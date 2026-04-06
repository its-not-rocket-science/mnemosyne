from fastapi import APIRouter, Depends, HTTPException

from backend.api.dependencies import get_plugin_registry
from backend.parsing.plugin_loader import PluginRegistry
from backend.schemas.parse import LessonResponse

router = APIRouter(tags=["lesson"])


@router.get("/lesson/{object_id}", response_model=LessonResponse)
async def get_lesson(
    object_id: str,
    language: str,
    registry: PluginRegistry = Depends(get_plugin_registry),
) -> LessonResponse:
    try:
        plugin = registry.get(language)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    lesson = plugin.get_lesson(object_id)
    if lesson is None:
        raise HTTPException(status_code=404, detail="Lesson object not found")

    title = f"{lesson.type.replace('_', ' ').title()}: {lesson.label}"
    content = _render_markdown(lesson.type, lesson.label, lesson.lesson_data)

    return LessonResponse(
        id=lesson.id,
        title=title,
        content_markdown=content,
        example_text=lesson.label,
    )


def _render_markdown(lesson_type: str, label: str, lesson_data: dict) -> str:
    lines = [f"## {label}", "", f"Type: **{lesson_type}**", ""]
    for key, value in lesson_data.items():
        lines.append(f"- **{key.replace('_', ' ').title()}**: {value}")
    lines.extend(["", "### Drill", "", "Choose the best interpretation, then rate your recall."])
    return "\n".join(lines)
