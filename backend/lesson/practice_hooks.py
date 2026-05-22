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


# ── Latin-script helpers ──────────────────────────────────────────────────────

def _latin_normalize(term: str) -> str:
    return _default_normalize(term).lower()


def _romance_variants(term: str, lemma: str | None) -> list[str]:
    base = _latin_normalize(term)
    lem = _latin_normalize(lemma or "")
    variants = [base, lem]
    # Spanish: hablarse → hablar (clitic appended)
    if base.endswith("se"):
        variants.append(base.removesuffix("se"))
    # French/Italian: se parler → parler, s'aimer → aimer (clitic prepended)
    if base.startswith("se "):
        variants.append(base.removeprefix("se "))
    elif base.startswith("s'"):
        variants.append(base.removeprefix("s'"))
    # Italian: si + verb
    if base.startswith("si "):
        variants.append(base.removeprefix("si "))
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


# ── German ────────────────────────────────────────────────────────────────────

def _german_normalize(term: str) -> str:
    return _default_normalize(term).lower()


def _german_variants(term: str, lemma: str | None) -> list[str]:
    base = _german_normalize(term)
    lem = _german_normalize(lemma or "")
    variants = [base, lem]
    # Accept ASCII equivalents for umlauts (common learner workaround)
    ascii_form = (
        base.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    )
    if ascii_form != base:
        variants.append(ascii_form)
    return [v for v in dict.fromkeys(variants) if v]


def _german_feedback(activity_type: str, fallback: str) -> str:
    if activity_type == "cloze_completion":
        return "Check case (Nom/Acc/Dat/Gen) and verb agreement before choosing the form."
    return fallback


# ── Russian ───────────────────────────────────────────────────────────────────

def _russian_normalize(term: str) -> str:
    # Strip combining acute accent (stress mark U+0301) used in Russian dictionaries
    return _default_normalize(term).lower().replace("́", "")


def _russian_variants(term: str, lemma: str | None) -> list[str]:
    base = _russian_normalize(term)
    lem = _russian_normalize(lemma or "")
    variants = [base, lem]
    # ё ↔ е equivalence (many keyboards omit ё)
    yo_form = base.replace("ё", "е")
    if yo_form != base:
        variants.append(yo_form)
    return [v for v in dict.fromkeys(variants) if v]


def _russian_feedback(activity_type: str, fallback: str) -> str:
    if activity_type == "cloze_completion":
        return "Check aspect (perfective/imperfective) and case before choosing the form."
    return fallback


# ── Japanese ──────────────────────────────────────────────────────────────────

def _japanese_normalize(term: str) -> str:
    return _default_normalize(term)  # mixed scripts — no lowercasing


def _japanese_variants(term: str, lemma: str | None) -> list[str]:
    base = _japanese_normalize(term)
    lem = _japanese_normalize(lemma or "")
    variants = [base, lem]
    # Accept without trailing particle は/が/を/に/で/と/も/か
    for particle in ("は", "が", "を", "に", "で", "と", "も", "か"):
        if base.endswith(particle):
            variants.append(base.removesuffix(particle))
            break
    return [v for v in dict.fromkeys(variants) if v]


# ── Arabic ────────────────────────────────────────────────────────────────────

def _arabic_normalize(term: str) -> str:
    # Strip tashkeel (U+064B–U+065F) and tatweel (U+0640)
    return "".join(
        c for c in _default_normalize(term)
        if not (0x064B <= ord(c) <= 0x065F) and c != "ـ"
    )


def _arabic_variants(term: str, lemma: str | None) -> list[str]:
    base = _arabic_normalize(term)
    lem = _arabic_normalize(lemma or "")
    variants = [base, lem]
    # Alef variants: أ إ آ ا ٱ → normalize all to bare ا for comparison
    alef_norm = (
        base.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا").replace("ٱ", "ا")
    )
    if alef_norm != base:
        variants.append(alef_norm)
    return [v for v in dict.fromkeys(variants) if v]


# ── Korean ────────────────────────────────────────────────────────────────────

def _korean_normalize(term: str) -> str:
    return _default_normalize(term)  # Hangul — no case, no standard ASCII fallback


def _korean_variants(term: str, lemma: str | None) -> list[str]:
    base = _korean_normalize(term)
    lem = _korean_normalize(lemma or "")
    return [v for v in dict.fromkeys([base, lem]) if v]


# ── Chinese ───────────────────────────────────────────────────────────────────

def _chinese_normalize(term: str) -> str:
    return _default_normalize(term)  # CJK — no lowercase, no transliteration here


def _chinese_variants(term: str, lemma: str | None) -> list[str]:
    base = _chinese_normalize(term)
    lem = _chinese_normalize(lemma or "")
    return [v for v in dict.fromkeys([base, lem]) if v]


# ── Dispatch table ────────────────────────────────────────────────────────────

HOOKS_BY_LANGUAGE: dict[str, PracticeHooks] = {
    "en": PracticeHooks(_latin_normalize,   _default_variants,  _default_cloze, _default_distractors, _latin_pattern,   _simple_feedback),
    "es": PracticeHooks(_latin_normalize,   _romance_variants,  _default_cloze, _default_distractors, _latin_pattern,   _simple_feedback),
    "fr": PracticeHooks(_latin_normalize,   _romance_variants,  _default_cloze, _default_distractors, _latin_pattern,   _simple_feedback),
    "it": PracticeHooks(_latin_normalize,   _romance_variants,  _default_cloze, _default_distractors, _latin_pattern,   _simple_feedback),
    "pt": PracticeHooks(_latin_normalize,   _romance_variants,  _default_cloze, _default_distractors, _latin_pattern,   _simple_feedback),
    "de": PracticeHooks(_german_normalize,  _german_variants,   _default_cloze, _default_distractors, _latin_pattern,   _german_feedback),
    "ru": PracticeHooks(_russian_normalize, _russian_variants,  _default_cloze, _default_distractors, _default_pattern, _russian_feedback),
    "ja": PracticeHooks(_japanese_normalize,_japanese_variants, _default_cloze, _default_distractors, _default_pattern, _default_feedback),
    "ar": PracticeHooks(_arabic_normalize,  _arabic_variants,   _default_cloze, _default_distractors, _default_pattern, _default_feedback),
    "ko": PracticeHooks(_korean_normalize,  _korean_variants,   _default_cloze, _default_distractors, _default_pattern, _default_feedback),
    "zh": PracticeHooks(_chinese_normalize, _chinese_variants,  _default_cloze, _default_distractors, _default_pattern, _default_feedback),
}


def hooks_for_language(language_code: str | None) -> PracticeHooks:
    if not language_code:
        return PracticeHooks(_default_normalize, _default_variants, _default_cloze, _default_distractors, _default_pattern, _default_feedback)
    return HOOKS_BY_LANGUAGE.get(language_code, PracticeHooks(_default_normalize, _default_variants, _default_cloze, _default_distractors, _default_pattern, _default_feedback))
