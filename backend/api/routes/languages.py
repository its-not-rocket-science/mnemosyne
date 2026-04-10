from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.api.dependencies import get_plugin_registry
from backend.parsing.plugin_loader import PluginRegistry
from backend.schemas.language import LanguageCapabilities

router = APIRouter(tags=["languages"])


@router.get("/languages", response_model=list[LanguageCapabilities])
async def list_languages(
    registry: PluginRegistry = Depends(get_plugin_registry),
) -> list[LanguageCapabilities]:
    """Return capability metadata for every active language plugin.

    Each entry describes the plugin's rendering requirements (direction,
    script_family) and the depth of analysis it provides (tokenization_mode,
    morphology_depth, lesson_modes_supported).  The frontend uses this to:

    - Populate the language selector.
    - Apply ``dir`` and ``lang`` attributes to sentence-card text.
    - Choose an appropriate font stack for non-Latin scripts.

    Results are sorted alphabetically by language code for stable output.
    """
    caps = registry.supported_languages()
    return sorted(caps.values(), key=lambda c: c.code)
