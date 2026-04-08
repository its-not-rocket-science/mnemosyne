from functools import lru_cache

from backend.core.database import get_db_session  # noqa: F401 — re-exported for routes
from backend.parsing.plugin_loader import PluginRegistry, load_plugins


@lru_cache
def get_plugin_registry() -> PluginRegistry:
    return load_plugins()
