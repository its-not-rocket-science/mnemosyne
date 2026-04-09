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
        code = plugin.language_code.lower().strip()
        if code in self._plugins:
            logger.warning(
                "Language %r already registered by %r; overwriting with %r.",
                code,
                type(self._plugins[code]).__name__,
                type(plugin).__name__,
            )
        self._plugins[code] = plugin

    def get(self, language_code: str) -> LanguagePlugin:
        normalized = language_code.lower().strip()
        if normalized not in self._plugins:
            available = ", ".join(sorted(self._plugins)) or "none"
            raise KeyError(
                f"Language '{language_code}' is not supported. "
                f"Available: {available}"
            )
        return self._plugins[normalized]

    def supported_languages(self) -> dict[str, dict[str, str]]:
        """Return metadata for every registered plugin.

        Keys are language codes; values are dicts with ``display_name`` and
        ``direction`` so the frontend can build a language selector without
        knowing plugin internals.
        """
        return {
            code: {
                "code": code,
                "display_name": p.display_name,
                "direction": p.direction,
            }
            for code, p in self._plugins.items()
        }

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
    allowed: set[str] | None = (
        {lang.lower().strip() for lang in settings.enabled_languages}
        if settings.enabled_languages is not None
        else None
    )
    registry = PluginRegistry()
    for module in _iter_plugin_modules(settings.plugin_package):
        plugin_factory = getattr(module, "create_plugin", None)
        if plugin_factory is None:
            continue
        try:
            plugin = plugin_factory()
            if allowed is not None and plugin.language_code.lower() not in allowed:
                logger.debug(
                    "Skipping plugin %r (language %r not in ENABLED_LANGUAGES).",
                    module.__name__, plugin.language_code,
                )
                continue
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
