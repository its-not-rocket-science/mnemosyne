"""Hindi morphological adapter — stanza (optional) with heuristic fallback.

When stanza is installed (poetry install --extras hindi):
  Full lemmatisation + morphological decomposition via stanza's Hindi UD model.
  Provides UPOS tags, UD feature strings, and neural lemmas.

  Install:
    poetry install --extras hindi
    # Model is downloaded automatically on first use (~100 MB).

Without stanza:
  Returns a surface-only HiMorphToken with source="heuristic".
  The Hindi plugin falls back to its suffix-rule analysis.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ── Data types ────────────────────────────────────────────────────────────────

@dataclass
class HiMorphToken:
    text: str          # surface form
    lemma: str         # stanza lemma or surface (heuristic)
    upos: str          # UD UPOS: VERB NOUN ADJ ADV ADP AUX PRON DET PART NUM PUNCT X …
    tense: str | None  # present | past | future
    aspect: str | None # habitual | perfective | converb
    gender: str | None # masculine | feminine
    number: str | None # singular | plural
    person: str | None # first | second | third
    case: str | None   # nominative | accusative | dative | locative | genitive | instrumental
    mood: str | None   # indicative | imperative | subjunctive | optative | conditional
    verb_form: str | None  # finite | participle | infinitive | converb
    voice: str | None  # active | passive
    source: str        # "stanza" | "heuristic"
    feats_raw: str | None = field(default=None)  # raw UD feats string


# ── UD feature → value mappings ───────────────────────────────────────────────

_TENSE_MAP: dict[str, str] = {
    "Pres": "present",
    "Past": "past",
    "Fut":  "future",
}

_ASPECT_MAP: dict[str, str] = {
    "Perf": "perfective",
    "Imp":  "habitual",    # imperfective → habitual (pedagogical label)
    "Hab":  "habitual",
    "Prog": "progressive",
}

_GENDER_MAP: dict[str, str] = {
    "Masc": "masculine",
    "Fem":  "feminine",
}

_NUMBER_MAP: dict[str, str] = {
    "Sing": "singular",
    "Plur": "plural",
}

_PERSON_MAP: dict[str, str] = {
    "1": "first",
    "2": "second",
    "3": "third",
}

_CASE_MAP: dict[str, str] = {
    "Nom": "nominative",
    "Acc": "accusative",
    "Dat": "dative",
    "Abl": "ablative",
    "Loc": "locative",
    "Gen": "genitive",
    "Ins": "instrumental",
    "Voc": "vocative",
    "Erg": "ergative",
}

_MOOD_MAP: dict[str, str] = {
    "Ind": "indicative",
    "Imp": "imperative",
    "Sub": "subjunctive",
    "Opt": "optative",
    "Cnd": "conditional",
}

_VERBFORM_MAP: dict[str, str] = {
    "Fin":  "finite",
    "Part": "participle",
    "Inf":  "infinitive",
    "Conv": "converb",
}


def _parse_feats(feats: str | None) -> dict:
    """Parse UD feats string into feature dict."""
    f: dict[str, str] = {}
    if feats:
        for part in feats.split("|"):
            k, _, v = part.partition("=")
            # Some values are comma-separated (e.g. "Case=Acc,Dat")
            f[k] = v.split(",")[0]  # take first value

    return {
        "tense":     _TENSE_MAP.get(f.get("Tense", ""), None),
        "aspect":    _ASPECT_MAP.get(f.get("Aspect", ""), None),
        "gender":    _GENDER_MAP.get(f.get("Gender", ""), None),
        "number":    _NUMBER_MAP.get(f.get("Number", ""), None),
        "person":    _PERSON_MAP.get(f.get("Person", ""), None),
        "case":      _CASE_MAP.get(f.get("Case", ""), None),
        "mood":      _MOOD_MAP.get(f.get("Mood", ""), None),
        "verb_form": _VERBFORM_MAP.get(f.get("VerbForm", ""), None),
        "voice":     f.get("Voice", "").lower() or None,
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
            "hi",
            processors="tokenize,pos,lemma",
            logging_level="WARN",
            download_method=None,   # don't auto-download at load time
        )
        logger.info("stanza Hindi pipeline loaded")
    except Exception as exc:
        # Model not yet downloaded — try with auto-download.
        try:
            import stanza  # noqa: PLC0415
            stanza.download("hi", processors="tokenize,pos,lemma", logging_level="WARN")
            _nlp = stanza.Pipeline(
                "hi",
                processors="tokenize,pos,lemma",
                logging_level="WARN",
            )
            logger.info("stanza Hindi pipeline loaded (after model download)")
        except Exception as exc2:
            _nlp = None
            logger.info("stanza unavailable — Hindi plugin in heuristic mode: %s", exc2)
    return _nlp


def is_available() -> bool:
    return _get_nlp() is not None


# ── Public API ────────────────────────────────────────────────────────────────

def analyze_sentence(text: str) -> list[HiMorphToken]:
    """Analyse all word tokens in *text* and return one HiMorphToken per word.

    Uses stanza when available; returns an empty list (triggering heuristic
    fallback) otherwise.
    """
    nlp = _get_nlp()
    if nlp is None:
        return []
    try:
        doc = nlp(text)  # type: ignore[operator]
        tokens: list[HiMorphToken] = []
        for sent in doc.sentences:
            for word in sent.words:
                feats = _parse_feats(word.feats)
                tokens.append(HiMorphToken(
                    text=word.text,
                    lemma=word.lemma or word.text,
                    upos=word.upos or "X",
                    tense=feats["tense"],
                    aspect=feats["aspect"],
                    gender=feats["gender"],
                    number=feats["number"],
                    person=feats["person"],
                    case=feats["case"],
                    mood=feats["mood"],
                    verb_form=feats["verb_form"],
                    voice=feats["voice"],
                    source="stanza",
                    feats_raw=word.feats,
                ))
        return tokens
    except Exception as exc:
        logger.debug("stanza analysis failed: %s", exc)
        return []
