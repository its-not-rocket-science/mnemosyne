"""Finnish plugin — stanza UD primary, fi_core_news_sm (spaCy) fallback.

Registers as ``language_code = "fi"``.

─────────────────────────────────────────────────────────────────────────────
WHAT THIS PLUGIN EXTRACTS
─────────────────────────────────────────────────────────────────────────────

**Vocabulary** — open-class content words (NOUN, ADJ, ADV, PROPN) and
non-finite VERB/AUX forms.

  lesson_data keys: lemma, pos, case*, number*, degree*, vowel_harmony,
                    possessive_suffix*, lemma_note*, cefr_level*

**Conjugation** — finite VERB and AUX tokens (VerbForm=Fin), annotated with:
  • tense (present/past/unknown)
  • mood (indicative/conditional/imperative/potential)
  • person (first/second/third/unknown)
  • number (singular/plural)
  • voice (active/passive)

  Finnish negation auxiliaries (ei/en/et/emme/ette/eivät) are emitted as
  conjugation objects with Polarity=Neg noted.

  lesson_data keys: lemma, surface, tense, mood, person, number, voice,
                    vowel_harmony, polarity*

─────────────────────────────────────────────────────────────────────────────
MODEL NOTES
─────────────────────────────────────────────────────────────────────────────

Primary: stanza Finnish UD model (tokenize+pos+lemma).
  Reliable 15-case detection, possessive-suffix features (Person[psor]/
  Number[psor]), correct POS for possessive-inflected nouns.

Fallback (no stanza): fi_core_news_sm (spaCy).
  Small model; lemmatization unreliable for consonant-gradation forms.
  Possessive-inflected nouns occasionally mislabelled as VERB.

Consonant-gradation alternations (d↔t, v↔p, ng↔nk, etc.) are flagged via
``lemma_note`` in both paths.
"""
from __future__ import annotations

import logging
import re
from functools import cached_property
from typing import Any

from backend.morphology import fi_adapter as _fi_stanza
from backend.morphology.fi_adapter import FiMorphToken as _FiMorphToken
from backend.plugins.cefr_vocab import (
    A1 as _CEFR_A1, A2 as _CEFR_A2, B1 as _CEFR_B1,
    B2 as _CEFR_B2, C1 as _CEFR_C1, C2 as _CEFR_C2,
)
from backend.schemas.language import LanguageCapabilities, NuanceCapabilities
from backend.schemas.parse import CandidateObject, CandidateSentenceResult, RelationHint

logger = logging.getLogger(__name__)

_FI_A1 = _CEFR_A1.get("fi", frozenset())
_FI_A2 = _CEFR_A2.get("fi", frozenset())
_FI_B1 = _CEFR_B1.get("fi", frozenset())
_FI_B2 = _CEFR_B2.get("fi", frozenset())
_FI_C1 = _CEFR_C1.get("fi", frozenset())
_FI_C2 = _CEFR_C2.get("fi", frozenset())

# ── POS filter ────────────────────────────────────────────────────────────────
# Skip closed-class function words that are not pedagogically useful as vocabulary.
_SKIP_POS = frozenset({
    "DET", "ADP", "CCONJ", "SCONJ", "CONJ", "PUNCT", "SPACE",
    "X", "SYM", "INTJ", "PART", "PRON",
})

# VerbForm values that indicate non-finite forms (treat as vocabulary).
_NON_FINITE_VERBFORMS = frozenset({"Inf", "Part", "Conv"})

# ── Display maps ──────────────────────────────────────────────────────────────
_CASE_MAP: dict[str, str] = {
    "Nom": "nominative",
    "Gen": "genitive",
    "Par": "partitive",
    "Acc": "accusative",
    "Ine": "inessive",
    "Ela": "elative",
    "Ill": "illative",
    "Ade": "adessive",
    "Abl": "ablative",
    "All": "allative",
    "Ess": "essive",
    "Tra": "translative",
    "Abe": "abessive",
    "Ins": "instructive",
    "Com": "comitative",
    "Loc": "locative",
}

_TENSE_MAP: dict[str, str] = {
    "Pres": "present",
    "Past": "past",
    "Fut":  "future",
}

_MOOD_MAP: dict[str, str] = {
    "Ind": "indicative",
    "Imp": "imperative",
    "Cnd": "conditional",
    "Pot": "potential",
    "Opt": "optative",
}

_PERSON_MAP: dict[str, str] = {
    "1": "first",
    "2": "second",
    "3": "third",
}

_VOICE_MAP: dict[str, str] = {
    "Act":  "active",
    "Pass": "passive",
}

# ── Vowel harmony ─────────────────────────────────────────────────────────────
_BACK_VOWELS  = frozenset("aouAOU")
_FRONT_VOWELS = frozenset("äöyÄÖY")


def _vowel_harmony(word: str) -> str:
    for ch in reversed(word):
        if ch in _BACK_VOWELS:
            return "back"
        if ch in _FRONT_VOWELS:
            return "front"
    return "back"


# ── Possessive suffix ─────────────────────────────────────────────────────────
# UD Finnish encodes possessive suffix as Person[psor] + Number[psor].
# Mapping: (person_digit, number_ud) -> display label
_POSS_LABEL: dict[tuple[str, str], str] = {
    ("1", "Sing"): "1sg", ("2", "Sing"): "2sg",
    ("3", "Sing"): "3sg", ("3", "Plur"): "3pl",
    ("1", "Plur"): "1pl", ("2", "Plur"): "2pl",
}

# Surface-form fallback: -mme / -nne / -nsa / -nsä are low-ambiguity.
# -ni and -si are omitted (high false-positive rate without UD features).
_POSS_SURFACE_RE = re.compile(r"(mme|nne|nsa|nsä)$", re.IGNORECASE)
_POSS_SURFACE_LABEL: dict[str, str] = {
    "mme": "1pl", "nne": "2pl", "nsa": "3sg/3pl", "nsä": "3sg/3pl",
}


def _possessive_suffix(tok: Any) -> str | None:
    """Return possessive-suffix label from UD features, or surface heuristic."""
    p_vals = tok.morph.get("Person[psor]")
    n_vals = tok.morph.get("Number[psor]")
    if p_vals and n_vals:
        label = _POSS_LABEL.get((p_vals[0], n_vals[0]))
        if label:
            return label
    m = _POSS_SURFACE_RE.search(tok.text)
    if m:
        return _POSS_SURFACE_LABEL.get(m.group().lower())
    return None


# ── Consonant gradation ───────────────────────────────────────────────────────
# Detect surface↔lemma alternations consistent with Finnish consonant gradation.
# Adds an informational note; does not reduce confidence (morphological features
# are still reliable; only lemma may be approximate).
_GRADATION_PAIRS = (
    ("d", "t"), ("v", "p"), ("ng", "nk"),
    ("mm", "mp"), ("nn", "nt"), ("ll", "lt"), ("rr", "rt"),
)


def _gradation_note(surface: str, lemma: str) -> str | None:
    s, l = surface.lower(), lemma.lower()
    if s == l:
        return None
    for weak, strong in _GRADATION_PAIRS:
        if weak in s and strong in l and weak not in l:
            return f"consonant gradation ({weak}↔{strong}): lemma is the strong-grade base form"
    return None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _possessive_suffix_stanza(mt: "_FiMorphToken") -> str | None:
    """Return possessive-suffix label from stanza FiMorphToken."""
    if mt.poss_person and mt.poss_number:
        return _POSS_LABEL.get((mt.poss_person, mt.poss_number))
    m = _POSS_SURFACE_RE.search(mt.text)
    if m:
        return _POSS_SURFACE_LABEL.get(m.group().lower())
    return None


# UPOS tags treated as closed-class / non-pedagogical in both paths
_STANZA_SKIP_UPOS = frozenset({
    "DET", "ADP", "CCONJ", "SCONJ", "CONJ", "PUNCT", "SPACE",
    "X", "SYM", "INTJ", "PART", "PRON",
})


def _morph_first(tok: Any, feature: str) -> str | None:
    vals = tok.morph.get(feature)
    return vals[0] if vals else None


def _conj_canonical_form(
    lemma: str, tense: str, mood: str, person: str, number: str, voice: str
) -> str:
    return f"{lemma}:{tense}:{mood}:{person}:{number}:{voice}"


# ── Plugin ────────────────────────────────────────────────────────────────────

class FinnishPlugin:
    """Finnish full-morphology plugin — stanza primary, fi_core_news_sm fallback."""

    language_code = "fi"
    display_name  = "Finnish"
    direction     = "ltr"
    capabilities  = LanguageCapabilities(
        code="fi",
        display_name="Finnish",
        direction="ltr",
        script_family="latin",
        tokenization_mode="whitespace",
        morphology_depth="rich",
        lesson_modes_supported=["morphology", "vocabulary"],
        analysis_depth="full",
        segmentation_quality="medium",
        tokenization_quality="high",
        morphology_quality="medium",  # small model; lemmatization unreliable for some forms
        syntax_support=True,
        idiom_detection=False,
        tts_lang_tag="fi",
        transliteration_scheme=None,
        tense_pool=["present", "past"],
        mood_pool=["indicative", "conditional", "imperative", "potential"],
        nuance_capabilities=NuanceCapabilities(
            idioms="none",
            phrase_families="none",
            literary_references="none",
            cultural_references="none",
            etymology="none",
            formality_register="none",
            grammar_nuance="partial",  # 15-case system + verb conjugation drilling
            pronunciation_tts="stub",
            transliteration="none",
            proverb_tradition="none",
            classical_or_scriptural_allusion="none",
            notes=(
                "stanza Finnish UD (primary): reliable 15-case system, possessive-suffix "
                "features (Person[psor]/Number[psor]), correct POS for possessive forms. "
                "fi_core_news_sm (spaCy) fallback when stanza unavailable. "
                "Consonant-gradation alternations (d↔t, v↔p, ng↔nk, etc.) flagged via "
                "lemma_note in both paths."
            ),
        ),
    )

    def __init__(self) -> None:
        self.lesson_store: dict[str, CandidateObject] = {}

    @cached_property
    def _nlp(self) -> Any:
        try:
            import spacy  # noqa: PLC0415
            return spacy.load("fi_core_news_sm", disable=["ner"])
        except ImportError as exc:
            raise RuntimeError("spaCy is not installed.  Run: pip install spacy") from exc
        except OSError as exc:
            raise RuntimeError(
                "spaCy model 'fi_core_news_sm' not found.  "
                "Run: python -m spacy download fi_core_news_sm"
            ) from exc

    # ── LanguagePlugin protocol ────────────────────────────────────────────────

    def analyze_text(self, text: str) -> list[CandidateSentenceResult]:
        if _fi_stanza.is_available():
            pairs = _fi_stanza.analyze_text(text.strip())
            return [self._analyze_stanza_sentence(s, toks) for s, toks in pairs]
        doc = self._nlp(text.strip())
        results = []
        for sent in doc.sents:
            sent_text = sent.text.strip()
            if not sent_text:
                continue
            results.append(self._analyze_tokens(sent_text, list(sent)))
        return results

    def split_sentences(self, text: str) -> list[str]:
        if _fi_stanza.is_available():
            return [s for s, _ in _fi_stanza.analyze_text(text.strip())]
        doc = self._nlp(text.strip())
        return [s.text.strip() for s in doc.sents if s.text.strip()]

    def analyze_sentence(self, sentence: str) -> CandidateSentenceResult:
        if _fi_stanza.is_available():
            tokens = _fi_stanza.analyze_sentence(sentence)
            if tokens:
                return self._analyze_stanza_sentence(sentence, tokens)
        doc = self._nlp(sentence)
        return self._analyze_tokens(sentence, list(doc))

    def get_lesson(self, object_id: str) -> CandidateObject | None:
        return self.lesson_store.get(object_id)

    # ── Stanza analysis path ──────────────────────────────────────────────────

    def _analyze_stanza_sentence(
        self, sentence: str, tokens: list[_FiMorphToken]
    ) -> CandidateSentenceResult:
        seen_vocab: set[str] = set()
        seen_conj:  set[str] = set()
        candidates: list[CandidateObject] = []
        candidates.extend(self._stanza_conjugations(tokens, seen_conj, seen_vocab))
        candidates.extend(self._stanza_vocabulary(tokens, seen_vocab))
        return CandidateSentenceResult(text=sentence, candidates=candidates)

    def _stanza_conjugations(
        self,
        tokens: list[_FiMorphToken],
        seen_conj: set[str],
        seen_vocab: set[str],
    ) -> list[CandidateObject]:
        candidates: list[CandidateObject] = []
        for mt in tokens:
            if mt.upos not in ("VERB", "AUX"):
                continue
            if mt.verb_form not in ("finite", None):
                continue
            # Require at least one finite indicator to avoid bare None-form nominals
            if mt.verb_form is None and mt.mood is None and mt.tense is None:
                continue

            lemma = mt.lemma
            if len(lemma) < 2:
                continue

            tense  = mt.tense  or "unknown"
            mood   = mt.mood   or "unknown"
            person = mt.person or "unknown"
            number = mt.number or "unknown"
            voice  = mt.voice  or "unknown"

            canonical = _conj_canonical_form(lemma, tense, mood, person, number, voice)
            if canonical in seen_conj:
                continue
            seen_conj.add(canonical)
            seen_vocab.add(lemma)

            lesson: dict[str, Any] = {
                "lemma":         lemma,
                "surface":       mt.text,
                "tense":         tense,
                "mood":          mood,
                "person":        person,
                "number":        number,
                "voice":         voice,
                "vowel_harmony": _vowel_harmony(mt.text),
            }
            if mt.polarity:
                lesson["polarity"] = mt.polarity

            candidates.append(CandidateObject(
                canonical_form=canonical,
                surface_form=mt.text,
                type="conjugation",
                label=mt.text,
                lesson_data=lesson,
                confidence=0.85,
                relation_hints=[RelationHint(
                    relation_type="conjugation_of",
                    target_canonical_form=lemma,
                    target_type="vocabulary",
                )],
            ))
        return candidates

    def _stanza_vocabulary(
        self,
        tokens: list[_FiMorphToken],
        seen: set[str],
    ) -> list[CandidateObject]:
        candidates: list[CandidateObject] = []
        for mt in tokens:
            if mt.upos in _STANZA_SKIP_UPOS:
                continue
            # Skip finite verb forms (handled as conjugations)
            if mt.upos in ("VERB", "AUX") and mt.verb_form == "finite":
                continue
            if mt.upos in ("VERB", "AUX") and mt.verb_form is None and (
                mt.mood is not None or mt.tense is not None
            ):
                continue

            lemma = mt.lemma
            if len(lemma) < 2 or lemma in seen:
                continue
            seen.add(lemma)

            data: dict[str, Any] = {
                "lemma":         lemma,
                "pos":           mt.upos.lower(),
                "vowel_harmony": _vowel_harmony(mt.text),
            }

            if mt.upos in ("NOUN", "PROPN"):
                if mt.case:
                    data["case"] = mt.case
                if mt.number:
                    data["number"] = mt.number
            elif mt.upos == "ADJ":
                if mt.case:
                    data["case"] = mt.case
                if mt.degree:
                    data["degree"] = mt.degree
            elif mt.upos in ("VERB", "AUX"):
                if mt.verb_form:
                    data["verb_form"] = mt.verb_form

            poss = _possessive_suffix_stanza(mt)
            if poss:
                data["possessive_suffix"] = poss

            grad = _gradation_note(mt.text, lemma)
            if grad:
                data["lemma_note"] = grad

            conf, conf_note = self._stanza_vocab_confidence(mt)
            cefr = (
                "A1" if lemma in _FI_A1 else
                "A2" if lemma in _FI_A2 else
                "B1" if lemma in _FI_B1 else
                "B2" if lemma in _FI_B2 else
                "C1" if lemma in _FI_C1 else
                "C2" if lemma in _FI_C2 else None
            )
            if cefr:
                data["cefr_level"] = cefr
            if conf_note:
                data["confidence_note"] = conf_note

            candidates.append(CandidateObject(
                canonical_form=lemma,
                surface_form=mt.text,
                type="vocabulary",
                label=mt.text,
                lesson_data=data,
                confidence=conf,
            ))
        return candidates

    def _stanza_vocab_confidence(self, mt: _FiMorphToken) -> tuple[float, str | None]:
        lemma = mt.lemma
        if mt.upos == "PROPN":
            return 0.60, "Proper noun: stanza morphology; lemma may be imprecise for names."
        if lemma in _FI_A1: return 0.90, None
        if lemma in _FI_A2: return 0.88, None
        if lemma in _FI_B1: return 0.86, None
        if lemma in _FI_B2: return 0.84, None
        if lemma in _FI_C1: return 0.82, None
        if lemma in _FI_C2: return 0.80, None
        if mt.feats_raw is None:
            return 0.75, None
        return 0.85, None

    # ── spaCy fallback path ───────────────────────────────────────────────────

    # ── Token analysis ────────────────────────────────────────────────────────

    def _analyze_tokens(
        self, sentence: str, tokens: list[Any]
    ) -> CandidateSentenceResult:
        seen_vocab: set[str] = set()
        seen_conj:  set[str] = set()

        candidates: list[CandidateObject] = []
        candidates.extend(self._extract_conjugations(tokens, seen_conj, seen_vocab))
        candidates.extend(self._extract_vocabulary(tokens, seen_vocab))

        return CandidateSentenceResult(text=sentence, candidates=candidates)

    # ── Conjugation ───────────────────────────────────────────────────────────

    def _extract_conjugations(
        self,
        tokens: list[Any],
        seen_conj: set[str],
        seen_vocab: set[str],
    ) -> list[CandidateObject]:
        candidates: list[CandidateObject] = []
        for tok in tokens:
            if tok.pos_ not in {"VERB", "AUX"}:
                continue
            verb_form = _morph_first(tok, "VerbForm")
            if verb_form in _NON_FINITE_VERBFORMS:
                continue
            # Must have VerbForm=Fin or be a negation auxiliary
            if verb_form not in ("Fin", None):
                continue

            lemma = tok.lemma_.lower()
            if len(lemma) < 2:
                continue

            tense  = _TENSE_MAP.get(_morph_first(tok, "Tense") or "",  "unknown")
            mood   = _MOOD_MAP.get(_morph_first(tok, "Mood") or "",   "unknown")
            person = _PERSON_MAP.get(_morph_first(tok, "Person") or "", "unknown")
            number = ("singular" if _morph_first(tok, "Number") == "Sing"
                      else "plural" if _morph_first(tok, "Number") == "Plur"
                      else "unknown")
            voice  = _VOICE_MAP.get(_morph_first(tok, "Voice") or "", "unknown")

            canonical = _conj_canonical_form(lemma, tense, mood, person, number, voice)
            if canonical in seen_conj:
                continue
            seen_conj.add(canonical)
            seen_vocab.add(lemma)

            lesson: dict[str, Any] = {
                "lemma":         lemma,
                "surface":       tok.text,
                "tense":         tense,
                "mood":          mood,
                "person":        person,
                "number":        number,
                "voice":         voice,
                "vowel_harmony": _vowel_harmony(tok.text),
            }
            polarity = _morph_first(tok, "Polarity")
            if polarity:
                lesson["polarity"] = polarity.lower()

            candidates.append(CandidateObject(
                canonical_form=canonical,
                surface_form=tok.text,
                type="conjugation",
                label=tok.text,
                lesson_data=lesson,
                confidence=0.80,
                relation_hints=[RelationHint(
                    relation_type="conjugation_of",
                    target_canonical_form=lemma,
                    target_type="vocabulary",
                )],
            ))
        return candidates

    # ── Vocabulary ────────────────────────────────────────────────────────────

    def _extract_vocabulary(
        self,
        tokens: list[Any],
        seen: set[str],
    ) -> list[CandidateObject]:
        candidates: list[CandidateObject] = []
        for tok in tokens:
            if tok.pos_ in _SKIP_POS or tok.is_punct or tok.is_space:
                continue

            verb_form = _morph_first(tok, "VerbForm")
            if tok.pos_ in {"VERB", "AUX"} and verb_form not in _NON_FINITE_VERBFORMS:
                continue

            lemma = tok.lemma_.lower()
            if len(lemma) < 2 or lemma in seen:
                continue
            seen.add(lemma)

            data: dict[str, Any] = {
                "lemma":         lemma,
                "pos":           tok.pos_.lower(),
                "vowel_harmony": _vowel_harmony(tok.text),
            }

            if tok.pos_ == "NOUN":
                if case := _CASE_MAP.get(_morph_first(tok, "Case") or ""):
                    data["case"] = case
                if number_raw := _morph_first(tok, "Number"):
                    data["number"] = "singular" if number_raw == "Sing" else "plural"

            elif tok.pos_ == "ADJ":
                if case := _CASE_MAP.get(_morph_first(tok, "Case") or ""):
                    data["case"] = case
                if degree := _morph_first(tok, "Degree"):
                    data["degree"] = degree.lower()

            elif tok.pos_ in {"VERB", "AUX"}:
                if verb_form:
                    data["verb_form"] = verb_form.lower()

            # Possessive suffix: apply to all vocabulary tokens. The small model
            # sometimes mislabels possessive-inflected nouns as ADV, so POS-gating
            # would miss them. -mme/-nne/-nsa/-nsä are low-ambiguity surface cues.
            poss = _possessive_suffix(tok)
            if poss:
                data["possessive_suffix"] = poss

            grad = _gradation_note(tok.text, lemma)
            if grad:
                data["lemma_note"] = grad

            confidence, confidence_note = self._vocab_confidence(tok, lemma)
            cefr = (
                "A1" if lemma in _FI_A1 else
                "A2" if lemma in _FI_A2 else
                "B1" if lemma in _FI_B1 else
                "B2" if lemma in _FI_B2 else
                "C1" if lemma in _FI_C1 else
                "C2" if lemma in _FI_C2 else None
            )
            if cefr:
                data["cefr_level"] = cefr
            if confidence_note:
                data["confidence_note"] = confidence_note

            candidates.append(CandidateObject(
                canonical_form=lemma,
                surface_form=tok.text,
                type="vocabulary",
                label=tok.text,
                lesson_data=data,
                confidence=confidence,
            ))
        return candidates

    def _vocab_confidence(self, tok: Any, lemma: str) -> tuple[float, str | None]:
        if tok.pos_ == "PROPN":
            return 0.60, (
                "Proper noun: POS tag from fi_core_news_sm; "
                "lemmatization and morphology less reliable for names."
            )
        if lemma in _FI_A1:
            return 0.90, None
        if lemma in _FI_A2:
            return 0.88, None
        if lemma in _FI_B1:
            return 0.86, None
        if tok.is_oov:
            if lemma in _FI_B2:
                return 0.84, None
            if lemma in _FI_C1:
                return 0.82, None
            if lemma in _FI_C2:
                return 0.80, None
            return 0.50, "word not in fi_core_news_sm vocabulary"
        return 0.80, None


def create_plugin() -> FinnishPlugin:
    return FinnishPlugin()
