from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies import get_db_session, get_plugin_registry
from backend.models import LearnableObjectRow
from backend.parsing.plugin_loader import PluginRegistry
from backend.schemas.parse import LessonResponse

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
        row = await db.get(LearnableObjectRow, object_id)
        if row is not None:
            return _build_response(
                id=row.id,
                obj_type=row.type,
                label=row.label,
                lesson_data=row.lesson_data,
            )
    except Exception:
        logger.warning("DB lesson lookup failed for %r", object_id, exc_info=True)

    # 2. Fall back to the plugin's in-memory store (populated during /parse).
    try:
        plugin = registry.get(language)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    lesson = plugin.get_lesson(object_id)
    if lesson is None:
        raise HTTPException(status_code=404, detail="Lesson object not found")

    return _build_response(
        id=lesson.id,
        obj_type=lesson.type,
        label=lesson.label,
        lesson_data=lesson.lesson_data,
    )


def _build_response(
    *,
    id: str,
    obj_type: str,
    label: str,
    lesson_data: dict,
) -> LessonResponse:
    title = f"{obj_type.replace('_', ' ').title()}: {label}"
    return LessonResponse(
        id=id,
        title=title,
        content_markdown=_render_markdown(obj_type, label, lesson_data),
        example_text=label,
    )


def _render_markdown(lesson_type: str, label: str, lesson_data: dict) -> str:
    lines = [f"## {label}", "", f"Type: **{lesson_type}**", ""]
    for key, value in lesson_data.items():
        lines.append(f"- **{key.replace('_', ' ').title()}**: {value}")
    lines.extend(["", "### Drill", "", "Choose the best interpretation, then rate your recall."])
    return "\n".join(lines)
