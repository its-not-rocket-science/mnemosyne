from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies import get_db_session, get_plugin_registry
from backend.lesson.generators import build_lesson
from backend.models import CanonicalObjectRow
from backend.parsing.plugin_loader import PluginRegistry
from backend.schemas.lesson import LessonResponse

logger = logging.getLogger(__name__)
router = APIRouter(tags=["lesson"])


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
            return build_lesson(
                object_id=row.id,
                obj_type=row.type,
                canonical_form=row.canonical_form,
                display_label=row.display_label,
                lesson_data=row.lesson_data or {},
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

    return build_lesson(
        object_id=object_id,
        obj_type=lo.type,
        canonical_form=lo.canonical_form,
        display_label=lo.label,
        lesson_data=lo.lesson_data or {},
    )
