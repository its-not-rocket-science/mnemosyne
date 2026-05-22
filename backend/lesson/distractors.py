"""Linguistically meaningful distractor generators.

Distractors should be morphologically plausible — forms a learner might
confuse with the correct answer, not arbitrary strings.

Priority order:
1. Paradigm cells — other inflected forms of the same lemma
2. ContrastNote.form_b — the commonly confused form
3. Language-specific near-morphology fallbacks
4. Legacy fallback (explanation text + "Not: {correct}") when nothing else works
"""
from __future__ import annotations

from backend.schemas.lesson import ContrastNote, MorphologyParadigm

# Common near-morphology confusions per language (fallback when no paradigm data).
_NEAR_MORPHOLOGY: dict[str, dict[str, list[str]]] = {
    "es": {
        "hablar": ["habla", "hablo", "hablé", "hablaba"],
        "ser":    ["es", "era", "fue", "soy"],
        "estar":  ["está", "estaba", "estuvo", "estoy"],
        "tener":  ["tiene", "tenía", "tuvo", "tengo"],
        "ir":     ["va", "iba", "fue", "voy"],
    },
    "de": {
        "sein":   ["ist", "war", "gewesen", "wäre"],
        "haben":  ["hat", "hatte", "gehabt", "hätte"],
        "werden": ["wird", "wurde", "geworden", "würde"],
    },
    "ru": {
        "быть":   ["есть", "был", "была", "были"],
        "делать": ["делает", "делал", "делала", "сделал"],
    },
    "fr": {
        "être":   ["est", "était", "fut", "sera"],
        "avoir":  ["a", "avait", "eut", "aura"],
        "aller":  ["va", "allait", "alla", "ira"],
    },
    "it": {
        "essere": ["è", "era", "fu", "sarà"],
        "avere":  ["ha", "aveva", "ebbe", "avrà"],
    },
    "pt": {
        "ser":    ["é", "era", "foi", "será"],
        "estar":  ["está", "estava", "esteve", "estará"],
    },
}


def build_paradigm_distractors(
    paradigms: list[MorphologyParadigm],
    correct: str,
    *,
    limit: int = 3,
) -> list[str]:
    """Return non-highlighted paradigm cell forms as distractors."""
    seen: set[str] = set()
    result: list[str] = []
    for p in paradigms:
        for cell in p.cells:
            if not cell.is_highlighted and cell.form and cell.form != correct:
                if cell.form not in seen:
                    seen.add(cell.form)
                    result.append(cell.form)
                if len(result) >= limit:
                    return result
    return result


def build_contrast_distractors(
    contrasts: list[ContrastNote],
    correct: str,
    *,
    limit: int = 3,
) -> list[str]:
    """Return form_b from contrast notes (commonly confused forms)."""
    return [
        c.form_b
        for c in contrasts
        if c.form_b and c.form_b != correct
    ][:limit]


def build_best_distractors(
    correct: str,
    lesson_explanation: str,
    text_basis: str,
    *,
    paradigms: list[MorphologyParadigm] | None = None,
    contrasts: list[ContrastNote] | None = None,
    language: str = "",
    lemma: str = "",
    limit: int = 3,
) -> list[str]:
    """Return the best available distractors, in priority order.

    Falls back to legacy behavior when no morphological data is available.
    """
    distractors: list[str] = []

    if paradigms:
        distractors.extend(build_paradigm_distractors(paradigms, correct))

    if contrasts:
        for d in build_contrast_distractors(contrasts, correct):
            if d not in distractors:
                distractors.append(d)

    if len(distractors) < limit and language and lemma:
        lang_pool = _NEAR_MORPHOLOGY.get(language, {})
        for form in lang_pool.get(lemma, []):
            if form != correct and form not in distractors:
                distractors.append(form)

    seen: set[str] = set()
    result: list[str] = []
    for d in distractors:
        if d and d != correct and d not in seen:
            seen.add(d)
            result.append(d)
        if len(result) >= limit:
            break

    if not result:
        return [lesson_explanation, text_basis, f"Not: {correct}"][:limit]

    return result
