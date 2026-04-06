import importlib
import logging
import pkgutil
from types import ModuleType

from backend.core.config import get_settings
from backend.parsing.plugin_interface import LanguagePlugin

logger = logging.getLogger(__name__)


class PluginRegistry:
    def __init__(self) -> None:
        self._plugins: dict[str, LanguagePlugin] = {}

    def register(self, plugin: LanguagePlugin) -> None:
        self._plugins[plugin.language_code] = plugin

    def get(self, language_code: str) -> LanguagePlugin:
        normalized = language_code.lower().strip()
        if normalized not in self._plugins:
            raise KeyError(f"No plugin registered for language '{language_code}'")
        return self._plugins[normalized]

    def all(self) -> dict[str, LanguagePlugin]:
        return dict(self._plugins)


def _iter_plugin_modules(package_name: str) -> list[ModuleType]:
    package = importlib.import_module(package_name)
    modules: list[ModuleType] = []
    for module_info in pkgutil.iter_modules(package.__path__, package.__name__ + "."):
        if module_info.name.endswith("__init__"):
            continue
        modules.append(importlib.import_module(module_info.name))
    return modules


def load_plugins() -> PluginRegistry:
    settings = get_settings()
    registry = PluginRegistry()
    for module in _iter_plugin_modules(settings.plugin_package):
        plugin_factory = getattr(module, "create_plugin", None)
        if plugin_factory is None:
            continue
        try:
            plugin = plugin_factory()
            registry.register(plugin)
            logger.info("Registered plugin %r (language: %r)", module.__name__, plugin.language_code)
        except Exception:
            logger.warning(
                "Could not load plugin from %r — skipping.  "
                "(Missing model?  Run the model download command.)",
                module.__name__,
                exc_info=True,
            )
    return registry
