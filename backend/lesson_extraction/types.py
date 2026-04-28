from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Mapping

LessonFamily = Literal[
    "vocabulary",
    "morphology",
    "syntax",
    "semantic_pattern",
    "script",
    "transliteration",
]

PedagogySource = Literal[
    "plugin",
    "lesson_extraction",
    "dictionary_summary",
    "heuristic",
]


@dataclass(frozen=True, slots=True)
class PedagogyTag:
    """Normalized lesson metadata attached under lesson_data["pedagogy"]."""

    family: LessonFamily
    skill: str
    level: int
    why_it_matters: str
    prompt_hint: str | None = None
    source: PedagogySource = "lesson_extraction"

    def as_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "family": self.family,
            "skill": self.skill,
            "level": self.level,
            "why_it_matters": self.why_it_matters,
            "source": self.source,
        }
        if self.prompt_hint:
            data["prompt_hint"] = self.prompt_hint
        return data


def with_pedagogy(
    lesson_data: Mapping[str, Any] | None,
    tag: PedagogyTag,
    *,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a copied lesson_data dict with a normalized pedagogy tag.

    Existing keys are preserved. Existing ``pedagogy`` metadata is preserved
    under ``pedagogy.previous`` so plugin-supplied metadata is not silently lost.
    """
    out: dict[str, Any] = dict(lesson_data or {})
    previous = out.get("pedagogy")
    out["pedagogy"] = tag.as_dict()
    if previous:
        out["pedagogy"]["previous"] = previous
    if extra:
        out.update(dict(extra))
    return out


def merge_lesson_data(base: Mapping[str, Any] | None, update: Mapping[str, Any] | None) -> dict[str, Any]:
    """Merge two lesson_data dictionaries without mutating either."""
    merged = dict(base or {})
    for key, value in (update or {}).items():
        if value is None:
            continue
        if key == "pedagogy" and key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            nested = dict(merged[key])
            nested.update(value)
            merged[key] = nested
        elif key not in merged or merged[key] in ("", [], {}, None):
            merged[key] = value
    return merged
