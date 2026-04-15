from functools import lru_cache

from fastapi import Header

from backend.core.database import get_db_session  # noqa: F401 — re-exported for routes
from backend.parsing.plugin_loader import PluginRegistry, load_plugins
from backend.srs.knowledge import DEFAULT_USER_ID


@lru_cache
def get_plugin_registry() -> PluginRegistry:
    return load_plugins()


def get_current_user(
    x_user_id: str | None = Header(default=None),
) -> str:
    """Resolve the current user from the ``X-User-Id`` request header.

    Falls back to ``DEFAULT_USER_ID`` (``"default"``) when the header is
    absent, preserving backward compatibility for local development and
    existing clients that do not send the header.

    This is the single injection point for future authentication.  To add
    JWT support, replace the ``Header`` extraction with a ``Bearer`` token
    decoder — all routes that ``Depends(get_current_user)`` update
    automatically without any other changes.
    """
    if x_user_id:
        stripped = x_user_id.strip()
        if stripped:
            return stripped
    return DEFAULT_USER_ID
