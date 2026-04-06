from functools import lru_cache

from backend.parsing.plugin_loader import PluginRegistry, load_plugins


@lru_cache
def get_plugin_registry() -> PluginRegistry:
    return load_plugins()
