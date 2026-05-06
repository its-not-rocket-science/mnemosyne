"""Arabic morphological adapter — CAMeL Tools with graceful fallback.

When camel-tools is installed and its built-in morphology database is
available, analyze_tokens() returns fully annotated MorphTokens: lemma,
POS, root, pattern, gloss, inflectional features (aspect, voice, mood,
person, number, gender, case), and proclitic fields (prc0/1/2).

When camel-tools is absent, every function still works — analyze_tokens()
returns surface-only MorphTokens with source="fallback".

Installation (optional — dictionary mode works without it):
    pip install camel-tools
    camel_data -i morphology-db-msa-r13

Example (CAMeL available):
    >>> toks = analyze_tokens(["كَتَبَ", "الطَّالِبُ"])
    >>> toks[0].root, toks[0].aspect
    ('ك.ت.ب', 'p')
    >>> toks[1].prc0
    'Al+'

Example (fallback):
    >>> toks = analyze_tokens(["كتب"])
    >>> toks[0].lemma, toks[0].source
    ('كتب', 'fallback')
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

try:
    from camel_tools.morphology.analyzer import Analyzer as _CamelAnalyzer
    from camel_tools.morphology.database import MorphologyDB as _MorphologyDB
    _CAMEL_MODULE_AVAILABLE = True
except ImportError:
    _CamelAnalyzer = None      # type: ignore[assignment,misc]
    _MorphologyDB = None       # type: ignore[assignment,misc]
    _CAMEL_MODULE_AVAILABLE = False

_SENTINEL = object()
_analyzer: Any = _SENTINEL   # module-level singleton; _SENTINEL = not yet attempted


@dataclass
class MorphToken:
    """One analyzed Arabic token."""
    text:    str
    lemma:   str
    pos:     str = "NOUN"
    root:    str = ""
    pattern: str = ""
    gloss:   str = ""
    person:  str = ""   # 1 | 2 | 3
    number:  str = ""   # s (sing) | d (dual) | p (plur)
    gender:  str = ""   # m (masc) | f (fem)
    case:    str = ""   # n (nom) | g (gen) | a (acc)
    voice:   str = ""   # a (active) | p (passive)
    aspect:  str = ""   # p (perfective) | i (imperfective) | c (command/imperative)
    mood:    str = ""   # i (indicative) | s (subjunctive) | j (jussive) | e (energetic)
    prc0:    str = ""   # definite article clitic, e.g. "Al+"
    prc1:    str = ""   # preposition clitic, e.g. "bi+", "li+", "ka+"
    prc2:    str = ""   # conjunction clitic, e.g. "wa+", "fa+"
    source:  str = "fallback"


_CAMEL_POS_TO_UD: dict[str, str] = {
    "noun": "NOUN", "adj": "ADJ", "verb": "VERB", "adv": "ADV",
    "prep": "ADP",  "conj": "CCONJ", "pron": "PRON", "det": "DET",
    "part": "PART", "num": "NUM",  "punc": "PUNCT", "interj": "INTJ",
    "abbrev": "X",  "foreign": "X",
}


def _camel_pos_to_ud(camel_pos: str) -> str:
    return _CAMEL_POS_TO_UD.get((camel_pos or "").lower(), "X")


def _pick_best_analysis(analyses: list[dict]) -> dict:
    """Prefer analyses with a real lexeme over NOAN (no-analysis marker)."""
    for a in analyses:
        lex = a.get("lex", "")
        if lex and lex != "NOAN":
            return a
    return analyses[0] if analyses else {}


def _try_load_analyzer() -> Any:
    """Attempt to load CAMeL Tools built-in MorphologyDB + Analyzer.

    Returns None on any failure (library absent, DB not downloaded, etc.).
    """
    if not _CAMEL_MODULE_AVAILABLE:
        return None
    try:
        db = _MorphologyDB.builtin_db()
        return _CamelAnalyzer(db)
    except Exception:
        return None


def _get_analyzer() -> Any:
    global _analyzer
    if _analyzer is _SENTINEL:
        _analyzer = _try_load_analyzer()
    return _analyzer


def is_available() -> bool:
    """True when CAMeL Tools is installed and the built-in DB loaded."""
    return _get_analyzer() is not None


def analyze_tokens(tokens: list[str]) -> list[MorphToken]:
    """Analyze a list of Arabic token strings.

    Uses CAMeL Tools when available. Falls back to surface-only MorphTokens
    (source="fallback") when the library is absent or raises.
    """
    analyzer = _get_analyzer()
    out: list[MorphToken] = []

    for token in tokens:
        if analyzer is not None:
            try:
                analyses = analyzer.analyze(token)
            except Exception:
                analyses = []

            if analyses:
                a = _pick_best_analysis(analyses)
                out.append(MorphToken(
                    text=token,
                    lemma=a.get("lex") or token,
                    pos=_camel_pos_to_ud(a.get("pos", "")),
                    root=a.get("root", ""),
                    pattern=a.get("pattern", ""),
                    gloss=a.get("gloss", ""),
                    person=str(a.get("per", "")),
                    number=str(a.get("num", "")),
                    gender=str(a.get("gen", "")),
                    case=str(a.get("cas", "")),
                    voice=str(a.get("vox", "")),
                    aspect=str(a.get("asp", "")),
                    mood=str(a.get("mod", "")),
                    prc0=str(a.get("prc0", "")),
                    prc1=str(a.get("prc1", "")),
                    prc2=str(a.get("prc2", "")),
                    source="camel_tools",
                ))
                continue

        out.append(MorphToken(text=token, lemma=token, source="fallback"))

    return out
