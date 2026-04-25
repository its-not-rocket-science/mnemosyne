from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies import get_db_session, get_plugin_registry
from backend.lesson.context import LessonContext
from backend.lesson.generators import build_lesson
from backend.lesson.providers import LessonProviders, VocabIndexGlossProvider
from backend.models import CanonicalObjectRow
from backend.parsing.plugin_loader import PluginRegistry
from backend.schemas.language import LessonMode, best_lesson_mode
from backend.schemas.lesson import LessonResponse

_PROVIDERS = LessonProviders(gloss=VocabIndexGlossProvider())

logger = logging.getLogger(__name__)
router = APIRouter(tags=["lesson"])


def _mode_for_language(registry: PluginRegistry, language: str) -> LessonMode:
    """Return the richest lesson mode the plugin for *language* supports.

    Falls back to ``"morphology"`` (the historic default) if the plugin
    pre-dates the capabilities system or if the language is not registered.
    """
    try:
        plugin = registry.get(language)
        caps = getattr(plugin, "capabilities", None)
        if caps is not None:
            return best_lesson_mode(caps.lesson_modes_supported)
    except KeyError:
        pass
    return "morphology"


def _context_for_language(registry: PluginRegistry, language: str) -> LessonContext:
    """Build a ``LessonContext`` from the registered plugin's capabilities.

    Falls back to ``LessonContext.unknown()`` when the language is not
    registered or the plugin pre-dates the capabilities system.
    """
    try:
        plugin = registry.get(language)
        caps = getattr(plugin, "capabilities", None)
        if caps is not None:
            return LessonContext.from_capabilities(caps)
    except KeyError:
        pass
    return LessonContext.unknown()


@router.get("/lesson/{object_id}", response_model=LessonResponse)
async def get_lesson(
    object_id: str,
    language: str,
    registry: PluginRegistry = Depends(get_plugin_registry),
    db: AsyncSession = Depends(get_db_session),
) -> LessonResponse:
    # 1. Database lookup — authoritative when the object has been parsed.
    try:
        row = await db.get(CanonicalObjectRow, object_id)
        if row is not None:
            mode    = _mode_for_language(registry, row.language)
            context = _context_for_language(registry, row.language)
            return build_lesson(
                object_id=row.id,
                obj_type=row.type,
                canonical_form=row.canonical_form,
                display_label=row.display_label,
                lesson_data=row.lesson_data or {},
                lesson_mode=mode,
                context=context,
                providers=_PROVIDERS,
            )
    except Exception:
        logger.warning("DB lesson lookup failed for %r", object_id, exc_info=True)

    # 2. Fall back to the plugin's in-memory store (populated during /parse).
    try:
        plugin = registry.get(language)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    lo = plugin.get_lesson(object_id)
    if lo is None:
        raise HTTPException(status_code=404, detail="Lesson object not found")

    mode    = _mode_for_language(registry, language)
    context = _context_for_language(registry, language)
    return build_lesson(
        object_id=object_id,
        obj_type=lo.type,
        canonical_form=lo.canonical_form,
        display_label=lo.label,
        lesson_data=lo.lesson_data or {},
        lesson_mode=mode,
        context=context,
        providers=_PROVIDERS,
    )
