import importlib
import logging
import pkgutil
from types import ModuleType

from backend.core.config import get_settings
from backend.parsing.plugin_interface import LanguagePlugin
from backend.schemas.language import LanguageCapabilities

logger = logging.getLogger(__name__)


class PluginRegistry:
    def __init__(self) -> None:
        self._plugins: dict[str, LanguagePlugin] = {}
        self._failed: dict[str, str] = {}
        """module_name → error summary for plugins that raised during load."""
        self._degraded: set[str] = set()
        """language codes whose NLP model failed warm-up — excluded from /languages."""

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

    def mark_degraded(self, code: str) -> None:
        """Mark a language as degraded so it is excluded from /languages."""
        self._degraded.add(code.lower().strip())

    def supported_languages(self) -> dict[str, LanguageCapabilities]:
        """Return capability metadata for every registered, non-degraded plugin.

        Keys are language codes; values are ``LanguageCapabilities`` objects.
        Plugins that pre-date the capabilities system are synthesised with
        conservative defaults so the rest of the stack always gets a typed
        object.  Languages whose NLP model failed warm-up are excluded.
        """
        result: dict[str, LanguageCapabilities] = {}
        for code, p in self._plugins.items():
            if code in self._degraded:
                continue
            caps = getattr(p, "capabilities", None)
            if caps is None:
                # Backward-compat fallback for plugins written before this
                # capability system.  Synthesise the minimum required fields.
                caps = LanguageCapabilities(
                    code=code,
                    display_name=p.display_name,
                    direction=p.direction,  # type: ignore[arg-type]  # pre-capabilities plugins expose direction as plain str; value is always "ltr" or "rtl" in practice
                    script_family="other",
                    tokenization_mode="whitespace",
                    morphology_depth="none",
                    lesson_modes_supported=["dictionary"],
                )
            result[code] = caps
        return result

    def failed_plugins(self) -> dict[str, str]:
        """Return a mapping of module_name → error summary for failed plugins.

        An empty dict means all plugins loaded successfully.
        """
        return dict(self._failed)

    def all(self) -> dict[str, LanguagePlugin]:
        return dict(self._plugins)


def _iter_plugin_modules(package_name: str) -> list[ModuleType]:
    package = importlib.import_module(package_name)
    modules: list[ModuleType] = []
    for module_info in pkgutil.iter_modules(package.__path__, package.__name__ + "."):
        if module_info.name.endswith("__init__"):  # pragma: no cover
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
        except Exception as exc:
            logger.warning(
                "Could not load plugin from %r — skipping.  "
                "(Missing model?  Run the model download command.)",
                module.__name__,
                exc_info=True,
            )
            registry._failed[module.__name__] = f"{type(exc).__name__}: {exc}"
    return registry
