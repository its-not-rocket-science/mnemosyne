"""Turkish morphological adapter — zeyrek (optional) with heuristic fallback.

When zeyrek is installed (poetry install --extras turkish):
  Full lemmatisation + morphological decomposition via the zeyrek rule-based
  analyzer (successor to Zemberek-NLP).  No neural network required; zeyrek
  is a pure rule-based FST analyzer (~5 MB).

  punkt_tab (NLTK tokenizer data) is downloaded automatically on first use.

  Install:
    poetry install --extras turkish
    # punkt_tab is downloaded automatically at first run (quiet, ~1 MB)

Without zeyrek:
  Returns a surface-only TrMorphToken with source="heuristic".
  The Turkish plugin falls back to its suffix-rule analysis.
"""
from __future__ import annotations

import contextlib
import io
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ── Data types ────────────────────────────────────────────────────────────────

@dataclass
class TrMorphToken:
    text: str              # surface form
    lemma: str             # base form (zeyrek) or surface (heuristic)
    pos: str               # "Verb" | "Noun" | "Adj" | "Adv" | "Pron" | "Conj" | …
    tense: str | None      # progressive | past_definite | past_evidential | aorist | future | present
    mood: str | None       # conditional | imperative | optative | necessitative
    person: str | None     # first | second | third
    number: str | None     # singular | plural
    case: str | None       # nominative | accusative | dative | ablative | locative | genitive | instrumental
    negation: bool         # True when Neg morpheme present
    verb_form: str | None  # "infinitive" for Inf1/Inf2/Inf3
    possessive: str | None # first_sg | second_sg | third_sg | first_pl | second_pl | third_pl
    source: str            # "zeyrek" | "heuristic"
    morphemes: list[str] = field(default_factory=list)  # raw zeyrek morpheme names


# ── Morpheme → feature mappings ───────────────────────────────────────────────

_TENSE_MAP: dict[str, str] = {
    "Prog1":   "progressive",     # -iyor (present progressive)
    "Prog2":   "progressive",     # -mekte (formal progressive)
    "Past":    "past_definite",   # -dı/-di (direct/witnessed past)
    "Narr":    "past_evidential", # -mış/-miş (narrative/hearsay past)
    "Aor":     "aorist",          # -ar/-er (simple present/habitual)
    "Fut":     "future",          # -ecek/-acak (finite future)
    "FutPart": "future",          # -ecek participial / adjectival future form
    "Pres":    "present",         # zero-morpheme present (often verbalized noun)
    "Cop":     "present",         # copula present
}

_MOOD_MAP: dict[str, str] = {
    "Cond":  "conditional",       # -sa/-se
    "Opt":   "optative",          # -a/-e
    "Imp":   "imperative",
    "Neces": "necessitative",     # -malı/-meli
}

_PERSON_MAP: dict[str, tuple[str, str]] = {
    "A1sg": ("first",  "singular"),
    "A2sg": ("second", "singular"),
    "A3sg": ("third",  "singular"),
    "A1pl": ("first",  "plural"),
    "A2pl": ("second", "plural"),
    "A3pl": ("third",  "plural"),
}

_CASE_MAP: dict[str, str] = {
    "Nom": "nominative",
    "Dat": "dative",
    "Acc": "accusative",
    "Abl": "ablative",
    "Loc": "locative",
    "Gen": "genitive",
    "Ins": "instrumental",
}

_POSS_MAP: dict[str, str] = {
    "P1sg": "first_sg",
    "P2sg": "second_sg",
    "P3sg": "third_sg",
    "P1pl": "first_pl",
    "P2pl": "second_pl",
    "P3pl": "third_pl",
}


def _parse_morphemes(morphemes: list[str]) -> dict:
    """Extract feature dict from zeyrek morpheme name list."""
    result: dict = {
        "tense": None, "mood": None, "person": None,
        "number": None, "case": None, "negation": False,
        "verb_form": None, "possessive": None,
    }
    for m in morphemes:
        if m in _TENSE_MAP and result["tense"] is None:
            result["tense"] = _TENSE_MAP[m]
        elif m in _MOOD_MAP and result["mood"] is None:
            result["mood"] = _MOOD_MAP[m]
        elif m in _PERSON_MAP:
            result["person"], result["number"] = _PERSON_MAP[m]
        elif m in _CASE_MAP and result["case"] is None:
            result["case"] = _CASE_MAP[m]
        elif m in _POSS_MAP:
            result["possessive"] = _POSS_MAP[m]
        elif m == "Neg":
            result["negation"] = True
        elif m in ("Inf1", "Inf2", "Inf3"):
            result["verb_form"] = "infinitive"
    return result


def _best_parse(analyses: list) -> object | None:
    """Pick best parse from zeyrek alternatives.

    Priority:
      1. Verb parse with a non-present tense (finite verb form — past, future, etc.)
      2. Any non-proper-noun parse
      3. Anything

    "Pres" tense is excluded from preference because in zeyrek it mainly marks
    verbalized nouns (noun + zero-derivation + present copula), not primary finite
    verb usage.  Finite progressives (Prog1/Prog2), definite past (Past), evidential
    (Narr), future (Fut), and aorist (Aor) are all non-present and get priority.
    """
    if not analyses:
        return None
    non_proper = [p for p in analyses if not p.pos.endswith("_Prop")]
    pool = non_proper if non_proper else analyses
    # Prefer finite verb form: pos must be Verb and tense must be non-present
    finite_verb = [
        p for p in pool
        if p.pos == "Verb"
        and any(
            m in _TENSE_MAP and _TENSE_MAP[m] != "present"
            for m in p.morphemes
        )
    ]
    return finite_verb[0] if finite_verb else pool[0]


# ── Lazy singleton ────────────────────────────────────────────────────────────

_SENTINEL: object = object()
_analyzer: object = _SENTINEL


def _get_analyzer() -> object | None:
    global _analyzer
    if _analyzer is not _SENTINEL:
        return _analyzer
    try:
        import nltk  # noqa: PLC0415
        nltk.download("punkt_tab", quiet=True)
        from zeyrek import MorphAnalyzer  # noqa: PLC0415
        _analyzer = MorphAnalyzer()
        logger.info("zeyrek loaded for Turkish morphological analysis")
    except Exception as exc:
        _analyzer = None
        logger.info("zeyrek unavailable — Turkish plugin in heuristic mode: %s", exc)
    return _analyzer


def _reset_analyzer() -> None:
    """Force re-initialisation of the zeyrek singleton on next access."""
    global _analyzer
    _analyzer = _SENTINEL


def is_available() -> bool:
    return _get_analyzer() is not None


def _run_analyze(analyzer: object, normalized: str) -> object | None:
    """Call analyzer.analyze and return the best parse, or None."""
    sink = io.StringIO()
    with contextlib.redirect_stderr(sink):
        raw = analyzer.analyze(normalized)  # type: ignore[attr-defined]
    if raw and raw[0]:
        return _best_parse(raw[0])
    return None


# ── Public API ────────────────────────────────────────────────────────────────

def analyze_token(word: str) -> TrMorphToken:
    """Return a TrMorphToken for a single Turkish word.

    Uses zeyrek when available; falls back to a surface-only token.

    Zeyrek has an FST state bug where analysing certain surface forms (e.g.
    'gidecek') corrupts subsequent analyses — the morphemes field is returned
    as the string 'Unk' instead of a list.  When we detect this (isinstance
    check), we reset the singleton and retry once with a fresh analyzer.  If
    the fresh analyzer also returns string morphemes the word is genuinely
    unknown to zeyrek and we fall through to the heuristic path.
    """
    analyzer = _get_analyzer()
    if analyzer is not None:
        try:
            # Normalize to Turkish-correct lowercase before analysis.
            # Zeyrek may not recognize sentence-initial capitals or dotted İ.
            normalized = word.replace("İ", "i").replace("I", "ı").lower()
            parse = _run_analyze(analyzer, normalized)

            if parse is not None and isinstance(parse.morphemes, str):
                # Corrupted FST state: morphemes came back as a plain string
                # instead of a list.  Reset the singleton and retry once.
                logger.debug(
                    "zeyrek FST corruption detected for %r — resetting analyzer", word
                )
                _reset_analyzer()
                fresh = _get_analyzer()
                if fresh is not None:
                    parse = _run_analyze(fresh, normalized)

            if parse is not None and not isinstance(parse.morphemes, str):
                feats = _parse_morphemes(list(parse.morphemes))
                pos = parse.pos.rstrip("_Prop")  # strip proper-noun marker
                return TrMorphToken(
                    text=word,
                    lemma=parse.lemma,
                    pos=pos,
                    source="zeyrek",
                    morphemes=list(parse.morphemes),
                    **feats,
                )
        except Exception as exc:
            logger.debug("zeyrek analysis failed for %r: %s", word, exc)

    # Heuristic fallback — surface only.
    return TrMorphToken(
        text=word,
        lemma=word.lower(),
        pos="Unknown",
        tense=None,
        mood=None,
        person=None,
        number=None,
        case=None,
        negation=False,
        verb_form=None,
        possessive=None,
        source="heuristic",
    )


def analyze_tokens(words: list[str]) -> list[TrMorphToken]:
    return [analyze_token(w) for w in words]
