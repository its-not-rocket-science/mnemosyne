from functools import lru_cache

from fastapi import Header, HTTPException, status

from backend.core.config import get_settings
from backend.core.database import get_db_session  # noqa: F401 — re-exported for routes
from backend.parsing.plugin_loader import PluginRegistry, load_plugins
from backend.srs.knowledge import DEFAULT_USER_ID

_401 = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Authentication required.",
    headers={"WWW-Authenticate": "Bearer"},
)
_401_invalid = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid or expired token.",
    headers={"WWW-Authenticate": "Bearer"},
)


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

    Steps 2 and 3 are only reached when ``settings.allow_dev_auth_fallback``
    is ``True`` (which mirrors ``DEBUG`` by default).  When it is ``False``
    (production), an invalid or absent Bearer token raises 401 immediately.
    """
    settings = get_settings()
    fallback = bool(settings.allow_dev_auth_fallback)

    # 1. Bearer JWT
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
        if token:
            from backend.auth.tokens import decode_access_token
            user_id = decode_access_token(token)
            if user_id:
                return user_id
        # Token present but invalid / empty.
        if not fallback:
            raise _401_invalid

    # 2. Plain header (dev / legacy)
    if x_user_id:
        stripped = x_user_id.strip()
        if stripped:
            if fallback:
                return stripped
            raise _401  # X-User-Id not accepted in strict mode

    # 3. No auth at all
    if fallback:
        return DEFAULT_USER_ID
    raise _401
