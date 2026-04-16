from functools import lru_cache

from fastapi import Header

from backend.core.database import get_db_session  # noqa: F401 — re-exported for routes
from backend.parsing.plugin_loader import PluginRegistry, load_plugins
from backend.srs.knowledge import DEFAULT_USER_ID


@lru_cache
def get_plugin_registry() -> PluginRegistry:
    return load_plugins()


def get_current_user(
    authorization: str | None = Header(default=None),
    x_user_id: str | None = Header(default=None),
) -> str:
    """Resolve the current user from the request.

    Resolution order
    ─────────────────
    1. ``Authorization: Bearer <jwt>`` — decoded JWT ``sub`` claim.
    2. ``X-User-Id: <id>`` — plain header (dev / legacy clients only).
    3. ``DEFAULT_USER_ID`` (``"default"``) — fallback for local runs with
       no auth configured.

    The JWT path is the production path.  The ``X-User-Id`` fallback remains
    for development convenience and for existing integration tests that pre-date
    JWT auth.  It is ignored when a valid Bearer token is present.
    """
    # 1. Bearer JWT
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
        if token:
            from backend.auth.tokens import decode_access_token
            user_id = decode_access_token(token)
            if user_id:
                return user_id
        # Token present but invalid — fall through to header fallback so dev
        # clients still work; a strict mode can raise 401 here in the future.

    # 2. Plain header (dev / legacy)
    if x_user_id:
        stripped = x_user_id.strip()
        if stripped:
            return stripped

    return DEFAULT_USER_ID
