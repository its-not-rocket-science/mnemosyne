"""Finnish morphological adapter — stanza (optional).

When the stanza Finnish model is available (downloaded via stanza.download('fi')):
  Full lemmatisation + 15-case system + verb morphology + possessive suffixes
  via stanza's Finnish UD model.

Without stanza:
  is_available() returns False; FinnishPlugin falls back to fi_core_news_sm (spaCy).

Install:
  poetry install --extras finnish   # (or: pip install stanza; stanza.download('fi'))
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ── Data types ────────────────────────────────────────────────────────────────

@dataclass
class FiMorphToken:
    text:        str
    lemma:       str
    upos:        str           # NOUN VERB ADJ ADV AUX PROPN PRON DET PART PUNCT …
    case:        str | None    # nominative | genitive | partitive | … (15 cases)
    number:      str | None    # singular | plural
    person:      str | None    # first | second | third
    poss_person: str | None    # raw Person[psor] digit ("1"/"2"/"3")
    poss_number: str | None    # raw Number[psor] value ("Sing"/"Plur")
    tense:       str | None    # present | past
    mood:        str | None    # indicative | conditional | imperative | potential | optative
    voice:       str | None    # active | passive
    verb_form:   str | None    # finite | infinitive | participle | converb
    degree:      str | None    # positive | comparative | superlative
    polarity:    str | None    # neg
    source:      str           # "stanza"
    feats_raw:   str | None    = field(default=None)


# ── UD feature maps ───────────────────────────────────────────────────────────

_CASE_MAP: dict[str, str] = {
    "Nom": "nominative",  "Gen": "genitive",    "Par": "partitive",
    "Acc": "accusative",  "Ine": "inessive",    "Ela": "elative",
    "Ill": "illative",    "Ade": "adessive",    "Abl": "ablative",
    "All": "allative",    "Ess": "essive",      "Tra": "translative",
    "Abe": "abessive",    "Ins": "instructive", "Com": "comitative",
}

_TENSE_MAP: dict[str, str] = {"Pres": "present", "Past": "past"}

_MOOD_MAP: dict[str, str] = {
    "Ind": "indicative", "Imp": "imperative",
    "Cnd": "conditional", "Pot": "potential", "Opt": "optative",
}

_VOICE_MAP: dict[str, str] = {"Act": "active", "Pass": "passive"}

_VERBFORM_MAP: dict[str, str] = {
    "Fin": "finite", "Inf": "infinitive",
    "Part": "participle", "Conv": "converb",
}

_DEGREE_MAP: dict[str, str] = {
    "Pos": "positive", "Cmp": "comparative", "Sup": "superlative",
}


def _parse_feats(feats: str | None) -> dict:
    f: dict[str, str] = {}
    if feats:
        for part in feats.split("|"):
            k, _, v = part.partition("=")
            f[k] = v
    return {
        "case":        _CASE_MAP.get(f.get("Case", ""), None),
        "number":      ("singular" if f.get("Number") == "Sing"
                        else "plural" if f.get("Number") == "Plur" else None),
        "person":      {"1": "first", "2": "second", "3": "third"}.get(f.get("Person", ""), None),
        "poss_person": f.get("Person[psor]") or None,
        "poss_number": f.get("Number[psor]") or None,
        "tense":       _TENSE_MAP.get(f.get("Tense", ""), None),
        "mood":        _MOOD_MAP.get(f.get("Mood", ""), None),
        "voice":       _VOICE_MAP.get(f.get("Voice", ""), None),
        "verb_form":   _VERBFORM_MAP.get(f.get("VerbForm", ""), None),
        "degree":      _DEGREE_MAP.get(f.get("Degree", ""), None),
        "polarity":    f.get("Polarity", "").lower() or None,
    }


# ── Lazy singleton ────────────────────────────────────────────────────────────

_SENTINEL: object = object()
_nlp: object = _SENTINEL


def _get_nlp() -> object | None:
    global _nlp
    if _nlp is not _SENTINEL:
        return _nlp
    try:
        import stanza  # noqa: PLC0415
        _nlp = stanza.Pipeline(
            "fi",
            processors="tokenize,pos,lemma",
            logging_level="WARN",
            download_method=None,
        )
        logger.info("stanza Finnish pipeline loaded")
    except Exception:
        try:
            import stanza  # noqa: PLC0415
            stanza.download("fi", processors="tokenize,pos,lemma", logging_level="WARN")
            _nlp = stanza.Pipeline(
                "fi",
                processors="tokenize,pos,lemma",
                logging_level="WARN",
            )
            logger.info("stanza Finnish pipeline loaded (after model download)")
        except Exception as exc2:
            _nlp = None
            logger.info("stanza unavailable for Finnish — using spaCy fallback: %s", exc2)
    return _nlp


def is_available() -> bool:
    return _get_nlp() is not None


# ── Token conversion ──────────────────────────────────────────────────────────

def _word_to_token(word: object) -> FiMorphToken:
    feats = _parse_feats(getattr(word, "feats", None))
    return FiMorphToken(
        text=getattr(word, "text", ""),
        lemma=(getattr(word, "lemma", None) or getattr(word, "text", "")).lower(),
        upos=getattr(word, "upos", None) or "X",
        source="stanza",
        feats_raw=getattr(word, "feats", None),
        **feats,
    )


# ── Public API ────────────────────────────────────────────────────────────────

def analyze_sentence(text: str) -> list[FiMorphToken]:
    """Analyze one sentence; return one FiMorphToken per word token."""
    nlp = _get_nlp()
    if nlp is None:
        return []
    try:
        doc = nlp(text)  # type: ignore[operator]
        return [_word_to_token(w) for sent in doc.sentences for w in sent.words]
    except Exception as exc:
        logger.debug("stanza Finnish sentence analysis failed: %s", exc)
        return []


def analyze_text(text: str) -> list[tuple[str, list[FiMorphToken]]]:
    """Analyze full text; return (sentence_text, tokens) per sentence."""
    nlp = _get_nlp()
    if nlp is None:
        return []
    try:
        doc = nlp(text)  # type: ignore[operator]
        return [
            (sent.text.strip(), [_word_to_token(w) for w in sent.words])
            for sent in doc.sentences
            if sent.text.strip()
        ]
    except Exception as exc:
        logger.debug("stanza Finnish text analysis failed: %s", exc)
        return []
