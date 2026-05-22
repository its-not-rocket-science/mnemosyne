"""Morphology-aware cloze prompt generator."""
from __future__ import annotations

from backend.schemas.lesson import MorphologyAxis

_AXIS_ORDER = ("person", "number", "tense", "mood", "aspect", "case", "gender", "voice")


def build_cloze_prompt(
    sentence: str,
    answer: str,
    axes: list[MorphologyAxis] | None = None,
) -> tuple[str, str | None]:
    """Return (prompt_with_blank, morphological_hint | None).

    The hint is a concise summary of active morphological axes, e.g.
    "3rd person singular present indicative". None when no meaningful
    axes are available.
    """
    if answer and answer in sentence:
        prompt = sentence.replace(answer, "____", 1)
    else:
        prompt = f"Complete the blank: ____ ({answer})"

    hint = _morphological_hint(axes or []) or None
    return prompt, hint


def _morphological_hint(axes: list[MorphologyAxis]) -> str:
    label_map: dict[str, str] = {}
    for ax in axes:
        if ax.axis in _AXIS_ORDER:
            label_map[ax.axis] = ax.label or ax.value
    return " ".join(label_map[k] for k in _AXIS_ORDER if k in label_map)
