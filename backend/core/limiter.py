"""Rate-limit infrastructure for Mnemosyne.

Key function
────────────
Limits are applied per authenticated user when a valid JWT or X-User-Id
header is present, and per remote IP otherwise.  This means:

  * Authenticated users share a single quota regardless of IP — they cannot
    bypass their limit by rotating IP addresses.
  * Anonymous / legacy-dev requests fall back to a per-IP limit.

Storage
───────
``slowapi`` uses the ``limits`` library under the hood.  The default storage
is in-memory, which means limits are per-process and reset on restart.
For multi-worker deployments, set ``SLOWAPI_STORAGE_URI`` to the Redis URL
(e.g. ``redis://redis:6379/1``) so all workers share the same counter.

429 handler
───────────
``rate_limit_exceeded_handler`` returns JSON ``{"detail": "..."}`` to match
FastAPI's standard error format.  Wire it via:

    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
"""
from __future__ import annotations

import logging

from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from backend.auth.tokens import decode_access_token

logger = logging.getLogger(__name__)


def _user_or_ip_key(request: Request) -> str:
    """Return a rate-limit bucket key for the request.

    Priority:
    1. ``Authorization: Bearer <jwt>`` — decode to user UUID.
    2. ``X-User-Id`` header — plain user identifier (dev/legacy).
    3. Remote IP address — anonymous fallback.
    """
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        token = auth[7:].strip()
        if token:
            user_id = decode_access_token(token)
            if user_id:
                return f"user:{user_id}"

    x_user = request.headers.get("X-User-Id", "").strip()
    if x_user:
        return f"user:{x_user}"

    return get_remote_address(request)


limiter = Limiter(key_func=_user_or_ip_key)


async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Return a JSON 429 body consistent with FastAPI's error format."""
    logger.warning(
        "rate limit exceeded: %s %s key=%s",
        request.method,
        request.url.path,
        _user_or_ip_key(request),
    )
    return JSONResponse(
        status_code=429,
        content={"detail": f"Rate limit exceeded: {exc.detail}. Try again later."},
        headers={"Retry-After": "60"},
    )
