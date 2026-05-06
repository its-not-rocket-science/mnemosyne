"""Static L1-language templates for lesson explanation prose.

Strategy
────────
Static string templates keyed by (template_key, l1_code).  No external
translation API: lesson explanations are short, parameterized, and must be
deterministic and zero-latency.  Adding a new L1 language means adding rows
to _TEMPLATES and _POS_LABELS; untranslated keys fall back to English so
partial coverage is always safe.

Usage
─────
    from backend.lesson import l10n

    pos = l10n.pos_label("noun", "es")          # "un sustantivo"
    text = l10n.t("vocab.simple", "es",
                  word="“amor”", pos=pos)
    # → '"amor" es un sustantivo.'

    lang = l10n.lang_name("Spanish", "es")      # "espa\xf1ol"

Fallback chain: requested l1 → "en" → "".  Callers that receive "" should
apply their own default prose (see formatters.py).

Adding a new L1
───────────────
1. Add entries to _TEMPLATES (each key) and _POS_LABELS.
2. Optionally add entries to _LANG_NAMES and _CONFIRMED_FEATURES_LABEL.
Untranslated entries silently fall back to English.
"""
from __future__ import annotations

# ── POS label phrases ──────────────────────────────────────────────────────────
# Each value is the full phrase used inside the explanation sentence, e.g.
#   EN  "is {pos}"  →  pos = "a noun"
#   ES  "es {pos}"  →  pos = "un sustantivo"
# Articles are embedded in the phrase so Spanish gender/article is correct.

_POS_LABELS: dict[str, dict[str, str]] = {
    "en": {
        "noun":          "a noun",
        "verb":          "a verb",
        "adjective":     "an adjective",
        "adverb":        "an adverb",
        "auxiliary verb":"an auxiliary verb",
        "proper noun":   "a proper noun",
        "word":          "a word",
    },
    "es": {
        "noun":          "un sustantivo",
        "verb":          "un verbo",
        "adjective":     "un adjetivo",
        "adverb":        "un adverbio",
        "auxiliary verb":"un verbo auxiliar",
        "proper noun":   "un nombre propio",
        "word":          "una palabra",
    },
}


def pos_label(pos_en: str, l1: str) -> str:
    """Localized POS phrase for *l1*, falling back to English."""
    return (
        _POS_LABELS.get(l1, {}).get(pos_en)
        or _POS_LABELS["en"].get(pos_en, pos_en)
    )


# ── Target-language names in L1 ────────────────────────────────────────────────
# Maps English language name → localized name in each L1.
# Keeps idiom explanations natural: "un modismo del español" not "del Spanish".

_LANG_NAMES: dict[str, dict[str, str]] = {
    "es": {
        "Arabic":     "árabe",
        "Chinese":    "chino",
        "English":    "inglés",
        "French":     "francés",
        "German":     "alemán",
        "Greek":      "griego",
        "Hebrew":     "hebreo",
        "Italian":    "italiano",
        "Japanese":   "japonés",
        "Korean":     "coreano",
        "Latin":      "latín",
        "Polish":     "polaco",
        "Portuguese": "portugués",
        "Russian":    "ruso",
        "Spanish":    "español",
        "Turkish":    "turco",
        "Ukrainian":  "ucraniano",
    },
}


def lang_name(english_name: str | None, l1: str) -> str | None:
    """Return *english_name* localized for *l1* display.

    Falls back to the English name when no translation is registered.
    Returns ``None`` when *english_name* is ``None``.
    """
    if english_name is None:
        return None
    return _LANG_NAMES.get(l1, {}).get(english_name, english_name)


# ── "morphological features" label ────────────────────────────────────────────

_FEATURES_FALLBACK: dict[str, str] = {
    "en": "morphological features",
    "es": "rasgos morfológicos",
}


def features_fallback(l1: str) -> str:
    return _FEATURES_FALLBACK.get(l1, _FEATURES_FALLBACK["en"])


# ── Sentence templates ─────────────────────────────────────────────────────────
# Keys: <builder>.<variant>  (builder matches the formatter function name).
# Values: Python .format() strings; parameter names are documented inline.
#
# IMPORTANT: English templates MUST produce output identical to the
# pre-l10n hardcoded strings so that l1="en" is a no-op behaviour change.

_TEMPLATES: dict[str, dict[str, str]] = {

    # ── vocabulary ────────────────────────────────────────────────────────────
    # {word}  quoted display label
    # {pos}   localized POS phrase, e.g. "a noun" / "un sustantivo"
    # {lemma} quoted lemma  [with_lemma variant only]
    "vocab.simple": {
        "en": "{word} is {pos}.",
        "es": "{word} es {pos}.",
    },
    "vocab.with_lemma": {
        "en": "{word} is {pos}. Its base form (lemma) is {lemma}.",
        "es": "{word} es {pos}. Su forma base (lema) es {lemma}.",
    },

    # ── conjugation ────────────────────────────────────────────────────────────
    # {word}, {person} (e.g. "third"), {number} (e.g. "singular"),
    # {tense}, {mood}, {lemma} — grammatical labels kept in English for MVP
    "conj.full": {
        "en": "{word} is the {person}-person {number} {tense} {mood} form of {lemma}.",
        "es": "{word} es la forma {tense} {mood} de {person} persona {number} de {lemma}.",
    },
    "conj.simple": {
        "en": "{word} is a conjugated form of {lemma}.",
        "es": "{word} es una forma conjugada de {lemma}.",
    },

    # ── agreement ─────────────────────────────────────────────────────────────
    # {mod}, {mod_pos}, {noun}, {features}, {gender}, {number}
    "agree.main": {
        "en": "{mod} ({mod_pos}) and {noun} agree in {features}. The noun {noun} is {gender} {number}.",
        "es": "{mod} ({mod_pos}) y {noun} concuerdan en {features}. El sustantivo {noun} es {gender} {number}.",
    },

    # ── case_agreement ────────────────────────────────────────────────────────
    # {mod}, {mod_pos}, {noun}, {features}, {gender}, {number}, {case}
    "case.main": {
        "en": "{mod} ({mod_pos}) and {noun} agree in {features}. The noun {noun} is {gender} {number} in the {case} case.",
        "es": "{mod} ({mod_pos}) y {noun} concuerdan en {features}. El sustantivo {noun} es {gender} {number} en caso {case}.",
    },

    # ── idiom ─────────────────────────────────────────────────────────────────
    # {word}, {lang} (localized via lang_name()), {meaning}
    "idiom.with_lang_and_meaning": {
        "en": "{word} is a {lang} idiom meaning {meaning}.",
        "es": "{word} es un modismo del {lang} que significa {meaning}.",
    },
    "idiom.with_lang": {
        "en": "{word} is a {lang} idiomatic expression.",
        "es": "{word} es una expresión idiomática del {lang}.",
    },
    "idiom.meaning_only": {
        "en": "{word} means {meaning}.",
        "es": "{word} significa {meaning}.",
    },
    "idiom.plain": {
        "en": "{word} is an idiomatic expression.",
        "es": "{word} es una expresión idiomática.",
    },

    # ── grammar ────────────────────────────────────────────────────────────────
    # {pattern} (already quoted), {usage}
    "grammar.with_usage": {
        "en": "The pattern {pattern}: {usage}",
        "es": "El patrón {pattern}: {usage}",
    },
    "grammar.plain": {
        "en": "The grammatical pattern {pattern}.",
        "es": "El patrón gramatical {pattern}.",
    },

    # ── nuance ─────────────────────────────────────────────────────────────────
    # {word}, {type_label} (already lowercased)
    "nuance.exhibits": {
        "en": "{word} exhibits {type_label}.",
        "es": "{word} presenta {type_label}.",
    },

    # ── script ─────────────────────────────────────────────────────────────────
    # {char} (already quoted), {meaning}
    "script.with_meaning": {
        "en": "{char} — {meaning}.",
        "es": "{char} — {meaning}.",
    },
    "script.plain": {
        "en": "{char}",
        "es": "{char}",
    },

    # ── dictionary ─────────────────────────────────────────────────────────────
    # {word} (already quoted), {gloss}, {lang}
    "dict.with_gloss": {
        "en": "{word} — {gloss}.",
        "es": "{word} — {gloss}.",
    },
    "dict.with_lang": {
        "en": "{word} — {lang} vocabulary.",
        "es": "{word} — vocabulario {lang}.",
    },
    "dict.plain": {
        "en": "{word}",
        "es": "{word}",
    },

    # ── transliteration ────────────────────────────────────────────────────────
    # {native}, {roman} (both quoted), {scheme} (e.g. " (hepburn)" or ""), {meaning}
    "translit.with_meaning": {
        "en": "{native} is romanized as {roman}{scheme} and means {meaning}.",
        "es": "{native} se romaniza como {roman}{scheme} y significa {meaning}.",
    },
    "translit.plain": {
        "en": "{native} is romanized as {roman}{scheme}.",
        "es": "{native} se romaniza como {roman}{scheme}.",
    },
}


def t(key: str, l1: str, **kwargs: str) -> str:
    """Look up *(key, l1)* template, interpolate *kwargs*, return result.

    Fallback: English when *l1* not present; "" when *key* not found.
    Callers that receive "" should apply their own default prose.
    """
    entry = _TEMPLATES.get(key, {})
    tmpl = entry.get(l1) or entry.get("en", "")
    if not tmpl:
        return ""
    try:
        return tmpl.format(**kwargs)
    except KeyError:
        return tmpl
