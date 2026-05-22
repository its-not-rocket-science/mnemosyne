"""Real morphological transformation drill specs.

Priority order — uses whichever source has data, skips otherwise:
1. Paradigm cells — non-highlighted cells are real transformation targets
2. ContrastNote.example_b — the contrast sentence with the other form
3. EquivalentConstruction — produce the equivalent form

Never emits placeholder drills (expected = instruction text). Returns []
when no source provides verifiable data.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from backend.schemas.lesson import ContrastNote, EquivalentConstruction, MorphologyParadigm


@dataclass
class TransformationSpec:
    prompt: str
    expected: str
    source: str  # "paradigm" | "contrast" | "equivalent"
    alternatives: list[str] = field(default_factory=list)


def build_transformation_specs(
    paradigms: list[MorphologyParadigm],
    contrasts: list[ContrastNote],
    equivalents: list[EquivalentConstruction],
    *,
    lemma: str = "",
    limit: int = 2,
) -> list[TransformationSpec]:
    """Build transformation specs from lesson morphology data.

    Returns [] when none of the sources have usable real data.
    """
    specs: list[TransformationSpec] = []

    highlighted_forms = {
        cell.form
        for p in paradigms
        for cell in p.cells
        if cell.is_highlighted
    }

    for paradigm in paradigms:
        if len(specs) >= limit:
            break
        non_highlighted = [c for c in paradigm.cells if not c.is_highlighted and c.form]
        for cell in non_highlighted:
            if len(specs) >= limit:
                break
            axes_desc = _axes_description(cell.axes)
            if not axes_desc:
                continue
            lemma_part = f" of “{lemma}”" if lemma else ""
            specs.append(TransformationSpec(
                prompt=f"Give the {axes_desc} form{lemma_part}.",
                expected=cell.form,
                source="paradigm",
                alternatives=list(highlighted_forms - {cell.form}),
            ))

    for c in contrasts:
        if len(specs) >= limit:
            break
        if not c.example_b:
            continue
        specs.append(TransformationSpec(
            prompt=f"Rewrite using “{c.form_b}” instead of “{c.form_a}”.",
            expected=c.example_b,
            source="contrast",
            alternatives=[c.example_a] if c.example_a else [],
        ))

    for eq in equivalents:
        if len(specs) >= limit:
            break
        if not eq.construction:
            continue
        note_part = f" ({eq.note})" if eq.note else ""
        specs.append(TransformationSpec(
            prompt=f"Rewrite using an equivalent construction{note_part}.",
            expected=eq.construction,
            source="equivalent",
        ))

    return specs


def _axes_description(axes: dict[str, str]) -> str:
    order = ("person", "number", "tense", "mood", "case", "gender", "aspect")
    parts = [axes[k] for k in order if k in axes]
    return " ".join(parts)
