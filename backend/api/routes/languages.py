from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.parsing.plugin_loader import PluginRegistry
from backend.api.dependencies import get_plugin_registry

router = APIRouter(tags=["languages"])


@router.get("/languages")
async def list_languages(
    registry: PluginRegistry = Depends(get_plugin_registry),
) -> list[dict[str, str]]:
    """Return the list of active language plugins.

    Each entry has ``code`` (BCP-47 language tag), ``display_name``
    (human-readable), and ``direction`` (``"ltr"`` or ``"rtl"``).
    Sorted alphabetically by code for stable output.
    """
    langs = registry.supported_languages()
    return sorted(langs.values(), key=lambda x: x["code"])
