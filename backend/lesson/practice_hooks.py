from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PracticeHooks:
    normalize_term: callable
    answer_variants: callable
    cloze_prompt: callable
    distractors: callable
    detect_pattern: callable
    feedback_text: callable


def _default_normalize(term: str) -> str:
    return (term or "").strip()


def _default_variants(term: str, lemma: str | None) -> list[str]:
    values = [_default_normalize(term), _default_normalize(lemma or "")]
    return [v for v in dict.fromkeys(values) if v]


def _default_cloze(sentence: str, answer: str) -> str:
    if answer and answer in sentence:
        return sentence.replace(answer, "____", 1)
    return f"Complete the blank: ____ ({answer})"


def _default_distractors(expected: str, lesson_explanation: str, text_basis: str) -> list[str]:
    return [lesson_explanation, text_basis, f"Not: {expected}"]


def _default_pattern(annotations: list[str]) -> str | None:
    return None


def _default_feedback(activity_type: str, fallback: str) -> str:
    return fallback


def _latin_normalize(term: str) -> str:
    return _default_normalize(term).lower()


def _romance_variants(term: str, lemma: str | None) -> list[str]:
    base = _latin_normalize(term)
    lem = _latin_normalize(lemma or "")
    variants = [base, lem]
    # Spanish: hablarse → hablar (clitic appended)
    if base.endswith("se"):
        variants.append(base.removesuffix("se"))
    # French: se parler → parler, s'aimer → aimer (clitic prepended)
    if base.startswith("se "):
        variants.append(base.removeprefix("se "))
    elif base.startswith("s'"):
        variants.append(base.removeprefix("s'"))
    return [v for v in dict.fromkeys(variants) if v]


def _latin_pattern(annotations: list[str]) -> str | None:
    for line in annotations:
        words = [w.strip(".,;:!?()[]{}\"'").lower() for w in line.split()]
        for w in words:
            if len(w) > 2 and words.count(w) > 1:
                return w
    return None


def _simple_feedback(activity_type: str, fallback: str) -> str:
    if activity_type == "cloze_completion":
        return "Use morphology and nearby context clues before translating directly."
    return fallback


HOOKS_BY_LANGUAGE: dict[str, PracticeHooks] = {
    "en": PracticeHooks(_latin_normalize, _default_variants, _default_cloze, _default_distractors, _latin_pattern, _simple_feedback),
    "es": PracticeHooks(_latin_normalize, _romance_variants, _default_cloze, _default_distractors, _latin_pattern, _simple_feedback),
    "fr": PracticeHooks(_latin_normalize, _romance_variants, _default_cloze, _default_distractors, _latin_pattern, _simple_feedback),
}


def hooks_for_language(language_code: str | None) -> PracticeHooks:
    if not language_code:
        return PracticeHooks(_default_normalize, _default_variants, _default_cloze, _default_distractors, _default_pattern, _default_feedback)
    return HOOKS_BY_LANGUAGE.get(language_code, PracticeHooks(_default_normalize, _default_variants, _default_cloze, _default_distractors, _default_pattern, _default_feedback))

