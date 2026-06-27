"""Hebrew morphological adapter — HebSpaCy with heuristic Semitic fallback.

When heb_spacy (he_dep_ud_hybrid model) is installed, analyze_tokens()
returns fully annotated MorphTokens: lemma, POS, binyan, tense, person,
number, gender, verb_form, and construct state.

When HebSpaCy is absent (the common case), every function still works —
the fallback applies heuristic inseparable-prefix stripping and a tiny
lexicon of common root/binyan/tense hints.  This is sufficient for the
prefix_decomposition nuance signal and limited binyan/verb-template notes in
backend.nuance.he.

Installation (optional — install the he_dep_ud_hybrid spaCy model by whatever
distribution the Hebrew NLP community provides; the adapter gates solely on
whether spacy.load("he_dep_ud_hybrid") succeeds):

Inseparable Hebrew prefixes handled by the fallback:
    Single-char  ב (be-), ו (ve-), ה (ha-), ל (le-), כ (ke-), מ (me-), ש (she-)
    Two-char     מה, שה, וה, בה, כה, לה  (preposition + definite article)

Example (HebSpaCy available):
    >>> toks = analyze_tokens(["כתב", "הספר"])
    >>> toks[0].binyan, toks[0].tense
    ("Pa'al", 'Past')
    >>> toks[1].prefix
    'ה'

Example (fallback):
    >>> toks = analyze_tokens(["בחנות"])
    >>> toks[0].lemma, toks[0].prefix, toks[0].source
    ('חנות', 'ב', 'heuristic')
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

try:
    import spacy as _spacy_mod
    _SPACY_AVAILABLE = True
except ImportError:
    _spacy_mod = None   # type: ignore[assignment]
    _SPACY_AVAILABLE = False

_SENTINEL = object()
_nlp: Any = _SENTINEL   # module-level singleton; _SENTINEL = not yet attempted


@dataclass
class MorphToken:
    """One analyzed Hebrew token."""
    text:      str
    lemma:     str
    pos:       str = "WORD"
    binyan:    str = ""   # Pa'al | Nif'al | Pi'el | Pu'al | Hitpa'el | Hif'il | Huf'al
    tense:     str = ""   # Past | Present | Future | Inf
    person:    str = ""   # 1 | 2 | 3
    number:    str = ""   # Sing | Plur | Dual
    gender:    str = ""   # Masc | Fem
    verb_form: str = ""   # Fin | Inf | Part
    construct: str = ""   # Con (construct / smichut state)
    root:      str = ""   # dotted consonantal root, e.g. כ.ת.ב
    prefix:    str = ""   # stripped inseparable prefix(es), e.g. "ב", "וה"
    source:    str = "fallback"


# Checked longest-first so "מה" beats "מ", "שה" beats "ש", etc.
_INSEP_PREFIXES: tuple[str, ...] = (
    "מה", "שה", "וה", "בה", "כה", "לה",
    "ב", "ו", "ה", "ל", "כ", "מ", "ש",
)

# Common complete words that begin with prefix letters but should not be split
# by the fallback. This keeps the spike useful without claiming real parsing.
_PREFIX_FALSE_POSITIVE_BLOCKLIST: frozenset[str] = frozenset({
    "שלום", "שלומך", "הוא", "היא", "כי", "כן", "לא", "מה", "מי",
})

_HEURISTIC_LEXICON: dict[str, dict[str, str]] = {
    "כתב": {"lemma": "כתב", "pos": "VERB", "root": "כ.ת.ב", "binyan": "Pa'al", "tense": "Past", "person": "3", "number": "Sing", "gender": "Masc", "verb_form": "Fin"},
    "כותב": {"lemma": "כתב", "pos": "VERB", "root": "כ.ת.ב", "binyan": "Pa'al", "tense": "Present", "number": "Sing", "gender": "Masc", "verb_form": "Part"},
    "קרא": {"lemma": "קרא", "pos": "VERB", "root": "ק.ר.א", "binyan": "Pa'al", "tense": "Past", "person": "3", "number": "Sing", "gender": "Masc", "verb_form": "Fin"},
    "הלך": {"lemma": "הלך", "pos": "VERB", "root": "ה.ל.ך", "binyan": "Pa'al", "tense": "Past", "person": "3", "number": "Sing", "gender": "Masc", "verb_form": "Fin"},
    "מכתב": {"lemma": "מכתב", "pos": "NOUN", "root": "כ.ת.ב", "binyan": "", "tense": ""},
}


def _extract_prefix(token: str) -> tuple[str, str]:
    """Strip the leading inseparable Hebrew prefix from *token*.

    Returns (remaining_word, prefix).  Requires the remaining word to be
    ≥ 3 characters to avoid stripping common short words (pronouns, etc.)
    that happen to start with a prefix letter.

    Examples:
        _extract_prefix("בחנות")  → ("חנות", "ב")
        _extract_prefix("לפארק")  → ("פארק", "ל")
        _extract_prefix("מהגינה") → ("גינה", "מה")
        _extract_prefix("הוא")    → ("הוא", "")     # remaining "וא" < 3 chars
        _extract_prefix("שלום")   → ("שלום", "")    # remaining "לום" = 3 — but "שלום"
    """
    if token in _PREFIX_FALSE_POSITIVE_BLOCKLIST:
        return token, ""
    for pfx in _INSEP_PREFIXES:
        if token.startswith(pfx) and len(token) - len(pfx) >= 3:
            return token[len(pfx):], pfx
    return token, ""


def _try_load_nlp() -> Any:
    if not _SPACY_AVAILABLE:
        return None
    try:
        return _spacy_mod.load("he_dep_ud_hybrid")
    except Exception:
        return None


def _get_nlp() -> Any:
    global _nlp
    if _nlp is _SENTINEL:
        _nlp = _try_load_nlp()
    return _nlp


def is_available() -> bool:
    """True when HebSpaCy is installed and he_dep_ud_hybrid loaded."""
    return _get_nlp() is not None


def _morph_first(tok: Any, key: str) -> str:
    """Return first value for morph feature *key*, or empty string."""
    vals = tok.morph.get(key)
    return vals[0] if vals else ""


def _fallback_analyze(tokens: list[str]) -> list[MorphToken]:
    """Heuristic-only analysis — always available without HebSpaCy.

    Strips inseparable prefixes to produce a candidate lemma and records
    the stripped prefix in MorphToken.prefix.  This fires the
    prefix_decomposition nuance signal in backend.nuance.he.
    """
    out = []
    for token in tokens:
        remaining, prefix = _extract_prefix(token)
        entry = _HEURISTIC_LEXICON.get(remaining)
        if entry:
            out.append(MorphToken(
                text=token,
                lemma=entry.get("lemma", remaining),
                pos=entry.get("pos", "WORD"),
                binyan=entry.get("binyan", ""),
                tense=entry.get("tense", ""),
                person=entry.get("person", ""),
                number=entry.get("number", ""),
                gender=entry.get("gender", ""),
                verb_form=entry.get("verb_form", ""),
                root=entry.get("root", ""),
                prefix=prefix,
                source="heuristic",
            ))
            continue
        out.append(MorphToken(
            text=token,
            lemma=remaining,
            prefix=prefix,
            source="heuristic",
        ))
    return out


def analyze_tokens(tokens: list[str]) -> list[MorphToken]:
    """Analyze a list of Hebrew token strings.

    Uses HebSpaCy when available; falls back to heuristic prefix stripping.
    The `prefix` field is populated in both modes.
    """
    nlp = _get_nlp()
    if nlp is None:
        return _fallback_analyze(tokens)

    doc = nlp(" ".join(tokens))
    out = []
    for tok in doc:
        _, prefix = _extract_prefix(tok.text)
        out.append(MorphToken(
            text=tok.text,
            lemma=tok.lemma_ or tok.text,
            pos=tok.pos_ or "WORD",
            binyan=_morph_first(tok, "Binyan"),
            tense=_morph_first(tok, "Tense"),
            person=_morph_first(tok, "Person"),
            number=_morph_first(tok, "Number"),
            gender=_morph_first(tok, "Gender"),
            verb_form=_morph_first(tok, "VerbForm"),
            construct=_morph_first(tok, "Definite"),
            prefix=prefix,
            source="heb_spacy",
        ))
    return out
