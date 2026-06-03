"""Turkish morphological adapter — stanza neural UD model (optional).

When the stanza Turkish model is available (downloaded via stanza.download('tr')):
  Full lemmatisation + case + tense/aspect + person/number + possessive stacking
  + evidential distinction (-dı vs -mış) via stanza's Turkish UD model.

Without stanza:
  is_available() returns False; TurkishPlugin falls back to zeyrek / heuristic.

Install:
  poetry install --extras turkish-stanza
  # or: pip install stanza; python -c "import stanza; stanza.download('tr')"
"""
from __future__ import annotations

import logging
import unicodedata
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ── Data types ────────────────────────────────────────────────────────────────

@dataclass
class TrStanzaMorphToken:
    text:        str
    lemma:       str
    upos:        str           # NOUN VERB ADJ ADV AUX PRON DET CCONJ SCONJ PUNCT …
    case:        str | None    # nominative | accusative | dative | ablative | locative | genitive | instrumental
    number:      str | None    # singular | plural
    person:      str | None    # first | second | third
    poss_person: str | None    # raw Person[psor] ("1"/"2"/"3")
    poss_number: str | None    # raw Number[psor] ("Sing"/"Plur")
    tense:       str | None    # aorist | progressive | past_definite | past_evidential | future | present
    mood:        str | None    # indicative | imperative | conditional | optative | necessitative
    polarity:    str | None    # pos | neg
    verb_form:   str | None    # vnoun | infinitive | participle | converb
    evidential:  str | None    # "nfh" when Evident=Nfh (-mış/-miş hearsay past)
    source:      str           # "stanza"
    feats_raw:   str | None    = field(default=None)


# ── UD feature maps ───────────────────────────────────────────────────────────

_CASE_MAP: dict[str, str] = {
    "Nom": "nominative",
    "Acc": "accusative",
    "Dat": "dative",
    "Abl": "ablative",
    "Loc": "locative",
    "Gen": "genitive",
    "Ins": "instrumental",
}

_MOOD_MAP: dict[str, str] = {
    "Ind":  "indicative",
    "Imp":  "imperative",
    "Cnd":  "conditional",
    "Opt":  "optative",
    "Nec":  "necessitative",
}

_VERBFORM_MAP: dict[str, str] = {
    "Vnoun": "vnoun",
    "Inf":   "infinitive",
    "Part":  "participle",
    "Conv":  "converb",
}

_POSS_PERSON_MAP: dict[str, str] = {
    "1": "first", "2": "second", "3": "third",
}
_POSS_NUMBER_MAP: dict[str, str] = {
    "Sing": "singular", "Plur": "plural",
}

# Possessive person+number → canonical label (matches existing zeyrek vocabulary)
_POSS_LABEL: dict[tuple[str, str], str] = {
    ("1", "Sing"): "first_sg",
    ("2", "Sing"): "second_sg",
    ("3", "Sing"): "third_sg",
    ("1", "Plur"): "first_pl",
    ("2", "Plur"): "second_pl",
    ("3", "Plur"): "third_pl",
}


def _parse_feats(feats: str | None) -> dict:
    f: dict[str, str] = {}
    if feats:
        for part in feats.split("|"):
            k, _, v = part.partition("=")
            f[k] = v

    # Derive tense from Tense + Aspect + Evident combination
    raw_tense  = f.get("Tense", "")
    raw_aspect = f.get("Aspect", "")
    raw_evid   = f.get("Evident", "")

    if raw_evid == "Nfh":
        tense = "past_evidential"
    elif raw_tense == "Past":
        tense = "past_definite"
    elif raw_aspect == "Prog":
        tense = "progressive"
    elif raw_aspect == "Hab":
        tense = "aorist"
    elif raw_tense == "Fut":
        tense = "future"
    elif raw_tense == "Pres":
        tense = "present"
    else:
        tense = None

    return {
        "case":        _CASE_MAP.get(f.get("Case", ""), None),
        "number":      ("singular" if f.get("Number") == "Sing"
                        else "plural" if f.get("Number") == "Plur" else None),
        "person":      {"1": "first", "2": "second", "3": "third"}.get(f.get("Person", ""), None),
        "poss_person": f.get("Person[psor]") or None,
        "poss_number": f.get("Number[psor]") or None,
        "tense":       tense,
        "mood":        _MOOD_MAP.get(f.get("Mood", ""), None),
        "polarity":    f.get("Polarity", "").lower() or None,
        "verb_form":   _VERBFORM_MAP.get(f.get("VerbForm", ""), None),
        "evidential":  raw_evid.lower() or None,
    }


def possessive_label(mt: "TrStanzaMorphToken") -> str | None:
    """Return canonical possessive label ("first_sg" etc.) or None."""
    if mt.poss_person and mt.poss_number:
        return _POSS_LABEL.get((mt.poss_person, mt.poss_number))
    return None


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
            "tr",
            processors="tokenize,mwt,pos,lemma",
            logging_level="WARN",
            download_method=None,
        )
        logger.info("stanza Turkish pipeline loaded")
    except Exception:
        try:
            import stanza  # noqa: PLC0415
            stanza.download("tr", processors="tokenize,mwt,pos,lemma", logging_level="WARN")
            _nlp = stanza.Pipeline(
                "tr",
                processors="tokenize,mwt,pos,lemma",
                logging_level="WARN",
            )
            logger.info("stanza Turkish pipeline loaded (after model download)")
        except Exception as exc2:
            _nlp = None
            logger.info("stanza unavailable for Turkish — using zeyrek/heuristic: %s", exc2)
    return _nlp


def is_available() -> bool:
    return _get_nlp() is not None


# ── Token conversion ──────────────────────────────────────────────────────────

def _word_to_token(word: object) -> TrStanzaMorphToken:
    feats = _parse_feats(getattr(word, "feats", None))
    raw_lemma = getattr(word, "lemma", None) or getattr(word, "text", "")
    # NFC-normalize before returning; let Turkish-aware callers (plugin's
    # _normalise_turkish) apply İ→i / I→ı mapping — Python's .lower() turns
    # U+0130 (İ) into "i̇" (decomposed), breaking substring checks.
    lemma = unicodedata.normalize("NFC", raw_lemma)
    return TrStanzaMorphToken(
        text=getattr(word, "text", ""),
        lemma=lemma,
        upos=getattr(word, "upos", None) or "X",
        source="stanza",
        feats_raw=getattr(word, "feats", None),
        **feats,
    )


# ── Public API ────────────────────────────────────────────────────────────────

def analyze_sentence(text: str) -> list[TrStanzaMorphToken]:
    """Analyze one sentence; return one TrStanzaMorphToken per word."""
    nlp = _get_nlp()
    if nlp is None:
        return []
    try:
        doc = nlp(text)  # type: ignore[operator]
        return [_word_to_token(w) for sent in doc.sentences for w in sent.words]
    except Exception as exc:
        logger.debug("stanza Turkish sentence analysis failed: %s", exc)
        return []


def analyze_text(text: str) -> list[tuple[str, list[TrStanzaMorphToken]]]:
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
        logger.debug("stanza Turkish text analysis failed: %s", exc)
        return []
