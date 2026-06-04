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

_LOCATION_CASES: dict[str, str] = {
    "inessive": "inside / in",
    "elative": "out of / from inside",
    "illative": "into",
    "adessive": "on / at",
    "ablative": "off / from",
    "allative": "onto / to",
}

_LOCATION_CASE_SUFFIXES: dict[str, tuple[str, ...]] = {
    "inessive": ("ssa", "ssä"),
    "elative": ("sta", "stä"),
    "illative": ("in", "an", "en", "on", "ön", "un", "yn", "seen"),
    "adessive": ("lla", "llä"),
    "ablative": ("lta", "ltä"),
    "allative": ("lle",),
}

_NEGATIVE_AUXILIARIES = frozenset({"en", "et", "ei", "emme", "ette", "eivät", "eivat"})



_POSSESSIVE_MEANING: dict[str, str] = {
    "1sg": "my",
    "2sg": "your (singular)",
    "3sg": "his/her",
    "1pl": "our",
    "2pl": "your (plural)",
    "3pl": "their",
    "3sg/3pl": "his/her/their",
}

_NEGATIVE_AUX_PERSON: dict[str, str] = {
    "en": "1sg",
    "et": "2sg",
    "ei": "3sg",
    "emme": "1pl",
    "ette": "2pl",
    "eivät": "3pl",
    "eivat": "3pl",
}

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
            grammar_nuance="partial",  # model-derived local cases, possessives, gradation, negation, passive/conditional
            pronunciation_tts="stub",
            transliteration="none",
            proverb_tradition="none",
            classical_or_scriptural_allusion="none",
            notes=(
                "stanza Finnish UD (primary): reliable 15-case system, possessive-suffix "
                "features (Person[psor]/Number[psor]), voice, polarity, and conditional mood. "
                "fi_core_news_sm (spaCy) fallback when stanza unavailable. Learner-facing "
                "grammar nuance emits shared fields (nuance_type, grammar_axis, surface, lemma, "
                "explanation, learner_level, drills). Consonant-gradation alternations "
                "(d↔t, v↔p, ng↔nk, etc.) flagged via lemma_note in both paths."
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
        candidates.extend(self._extract_nuance_candidates(candidates))
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
            poss_surface_fallback = bool(poss and not (mt.poss_person and mt.poss_number))
            if poss:
                data["possessive_suffix"] = poss
                if poss_surface_fallback:
                    data["possessive_suffix_source"] = "surface_fallback"

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
            elif data.get("possessive_suffix_source") == "surface_fallback":
                data["confidence_note"] = "Possessive suffix inferred from low-ambiguity surface ending, not UD Person[psor]/Number[psor]."

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
        candidates.extend(self._extract_nuance_candidates(candidates))

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
            poss_surface_fallback = bool(poss and not (_morph_first(tok, "Person[psor]") and _morph_first(tok, "Number[psor]")))
            if poss:
                data["possessive_suffix"] = poss
                if poss_surface_fallback:
                    data["possessive_suffix_source"] = "surface_fallback"

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
            elif data.get("possessive_suffix_source") == "surface_fallback":
                data["confidence_note"] = "Possessive suffix inferred from low-ambiguity surface ending, not UD Person[psor]/Number[psor]."

            candidates.append(CandidateObject(
                canonical_form=lemma,
                surface_form=tok.text,
                type="vocabulary",
                label=tok.text,
                lesson_data=data,
                confidence=confidence,
            ))
        return candidates

    # ── Grammar / nuance candidates ──────────────────────────────────────────

    def _extract_nuance_candidates(
        self,
        candidates: list[CandidateObject],
    ) -> list[CandidateObject]:
        """Emit Finnish grammar-nuance candidates from morphology already found.

        These objects power the Nuance tab and practice panels for high-value
        Finnish patterns: local cases, possessive suffixes, consonant gradation,
        passive voice, conditional mood, and the negative auxiliary paradigm.
        """
        out: list[CandidateObject] = []
        seen: set[str] = set()

        for cand in candidates:
            ld = cand.lesson_data or {}
            surface = cand.surface_form or cand.label or cand.canonical_form
            lemma = str(ld.get("lemma") or cand.canonical_form)

            if cand.type == "vocabulary":
                case = str(ld.get("case") or "")
                if case in _LOCATION_CASES:
                    suffix_hint = "/".join(_LOCATION_CASE_SUFFIXES.get(case, ()))
                    explanation = (
                        f"«{surface}» uses the Finnish {case} local case ({suffix_hint}), "
                        f"which expresses {_LOCATION_CASES[case]}. Finnish often encodes "
                        "English prepositions as case endings attached directly to the noun."
                    )
                    self._append_nuance(out, self._nuance_object(
                        seen=seen,
                        nuance_type="finnish_location_case",
                        grammar_axis="case",
                        key=f"{case}:{surface.lower()}",
                        surface=surface,
                        label=surface,
                        lemma=lemma,
                        explanation=explanation,
                        level="A2",
                        confidence=self._nuance_confidence(cand),
                        confidence_note=self._nuance_confidence_note(cand),
                        drill_prompt=(
                            f"What spatial meaning does the {case} case signal in «{surface}»?"
                        ),
                        drill_answer=_LOCATION_CASES[case],
                        extra={"case": case, "suffix_hint": suffix_hint},
                    ))

                poss = str(ld.get("possessive_suffix") or "")
                if poss:
                    poss_meaning = _POSSESSIVE_MEANING.get(poss, poss)
                    suffix = self._possessive_surface_suffix(surface, poss)
                    self._append_nuance(out, self._nuance_object(
                        seen=seen,
                        nuance_type="finnish_possessive_suffix",
                        grammar_axis="possessive_suffix",
                        key=f"{poss}:{surface.lower()}",
                        surface=surface,
                        label=surface,
                        lemma=lemma,
                        explanation=(
                            f"«{surface}» contains the possessive suffix -{suffix}. "
                            f"For this form it signals {poss_meaning} possession, so the possessor "
                            "is encoded inside the noun rather than as a separate word."
                        ),
                        level="A2",
                        confidence=self._nuance_confidence(cand),
                        confidence_note=self._nuance_confidence_note(cand),
                        drill_prompt=f"In «{surface}», whose possession does the suffix -{suffix} mark?",
                        drill_answer=poss_meaning,
                        extra={"possessive_suffix": poss, "possessive_meaning": poss_meaning},
                    ))

                grad = str(ld.get("lemma_note") or "")
                if "gradation" in grad.lower():
                    self._append_nuance(out, self._nuance_object(
                        seen=seen,
                        nuance_type="consonant_gradation",
                        grammar_axis="stem_alternation",
                        key=f"{lemma}:{surface.lower()}",
                        surface=surface,
                        label=surface,
                        lemma=lemma,
                        explanation=(
                            f"«{surface}» shows Finnish consonant gradation from the base «{lemma}». "
                            "Certain case endings weaken or alter the stem consonants, so the form is not "
                            "made by simply adding a suffix to an unchanged stem."
                        ),
                        level="A2",
                        confidence=self._nuance_confidence(cand),
                        confidence_note=self._nuance_confidence_note(cand),
                        drill_prompt=f"What stem-change pattern is visible between «{lemma}» and «{surface}»?",
                        drill_answer=grad,
                        extra={"lemma_note": grad},
                    ))

            if cand.type == "conjugation":
                voice = str(ld.get("voice") or "")
                tense = str(ld.get("tense") or "unknown")
                if voice == "passive":
                    self._append_nuance(out, self._nuance_object(
                        seen=seen,
                        nuance_type="finnish_passive_voice",
                        grammar_axis="voice",
                        key=f"{tense}:{surface.lower()}",
                        surface=surface,
                        label=surface,
                        lemma=lemma,
                        explanation=(
                            f"«{surface}» is Finnish passive voice ({tense}). It backgrounds the actor "
                            "and focuses on the action itself, often corresponding to English passive "
                            "or impersonal 'one/people' readings."
                        ),
                        level="A2",
                        confidence=self._nuance_confidence(cand),
                        confidence_note=self._nuance_confidence_note(cand),
                        drill_prompt=f"Is «{surface}» active or passive voice?",
                        drill_answer="passive",
                        extra={"tense": tense, "voice": voice},
                    ))

                mood = str(ld.get("mood") or "")
                if mood == "conditional":
                    self._append_nuance(out, self._nuance_object(
                        seen=seen,
                        nuance_type="finnish_conditional_mood",
                        grammar_axis="mood",
                        key=f"{lemma}:{surface.lower()}",
                        surface=surface,
                        label=surface,
                        lemma=lemma,
                        explanation=(
                            f"«{surface}» is in the Finnish conditional mood. Conditional forms often "
                            "express would/should-like meanings, hypotheticals, or polite softening."
                        ),
                        level="A2",
                        confidence=self._nuance_confidence(cand),
                        confidence_note=self._nuance_confidence_note(cand),
                        drill_prompt=f"What mood does «{surface}» use?",
                        drill_answer="conditional",
                        extra={"mood": mood},
                    ))

                polarity = str(ld.get("polarity") or "")
                lower_surface = surface.lower()
                if polarity == "neg" or lower_surface in _NEGATIVE_AUXILIARIES:
                    self._append_nuance(out, self._nuance_object(
                        seen=seen,
                        nuance_type="finnish_negative_auxiliary",
                        grammar_axis="polarity",
                        key=lower_surface,
                        surface=surface,
                        label=surface,
                        lemma=lemma,
                        explanation=(
                            f"«{surface}» is part of the Finnish negative auxiliary paradigm "
                            "(en, et, ei, emme, ette, eivät). Finnish negation conjugates for "
                            "person and number while the main verb appears in its negative stem form."
                        ),
                        level="A1",
                        confidence=self._nuance_confidence(cand),
                        confidence_note=self._nuance_confidence_note(cand),
                        drill_prompt=f"What does the Finnish auxiliary «{surface}» mark?",
                        drill_answer=f"negation ({_NEGATIVE_AUX_PERSON.get(lower_surface, 'negative auxiliary')})",
                        extra={"polarity": "neg", "negative_auxiliary_person": _NEGATIVE_AUX_PERSON.get(lower_surface)},
                    ))

        return out

    @staticmethod
    def _append_nuance(out: list[CandidateObject], obj: CandidateObject | None) -> None:
        if obj is not None:
            out.append(obj)

    def _nuance_object(
        self,
        *,
        seen: set[str],
        nuance_type: str,
        grammar_axis: str,
        key: str,
        surface: str,
        label: str,
        lemma: str,
        explanation: str,
        level: str,
        confidence: float,
        confidence_note: str | None,
        drill_prompt: str | None = None,
        drill_answer: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> CandidateObject | None:
        cf = f"nuance:fi:{nuance_type}:{key}"
        if cf in seen:
            return None
        seen.add(cf)
        lesson_data: dict[str, Any] = {
            "nuance_type": nuance_type,
            "grammar_axis": grammar_axis,
            "explanation": explanation,
            "note": explanation,
            "register": "neutral",
            "learner_level": level,
            "source": "stanza_ud" if confidence >= 0.80 and confidence_note is None else "surface_or_fallback_morphology",
            "surface": surface,
            "lemma": lemma,
        }
        if drill_prompt and drill_answer:
            lesson_data["drill_prompt"] = drill_prompt
            lesson_data["drill_answer"] = drill_answer
        if confidence_note:
            lesson_data["confidence_note"] = confidence_note
        if extra:
            lesson_data.update({k: v for k, v in extra.items() if v is not None})
        return CandidateObject(
            canonical_form=cf,
            surface_form=surface,
            type="nuance",
            label=label,
            lesson_data=lesson_data,
            confidence=confidence,
            relation_hints=[RelationHint(
                relation_type="nuance_of",
                target_canonical_form=lemma,
                target_type="vocabulary",
            )],
        )


    @staticmethod
    def _nuance_confidence(cand: CandidateObject) -> float:
        """Keep grammar-nuance confidence tied to the morphology source."""
        ld = cand.lesson_data or {}
        note = str(ld.get("confidence_note") or "")
        if "word not in fi_core_news_sm" in note:
            return 0.58
        if "Proper noun" in note:
            return 0.62
        if "surface ending" in note:
            return 0.68
        # Stanza-derived finite morphology and in-vocabulary spaCy morphology are
        # useful enough for learner-facing drills, but nuance should not exceed
        # the originating morphological object.
        base = cand.confidence if cand.confidence is not None else 0.70
        return min(float(base), 0.85)

    @staticmethod
    def _nuance_confidence_note(cand: CandidateObject) -> str | None:
        ld = cand.lesson_data or {}
        note = str(ld.get("confidence_note") or "")
        if note:
            return f"Derived from Finnish morphology with caveat: {note}"
        if cand.confidence is not None and cand.confidence < 0.80:
            return "Derived from lower-confidence Finnish morphology; verify in context."
        return None

    @staticmethod
    def _possessive_surface_suffix(surface: str, poss: str) -> str:
        lower = surface.lower()
        for suffix, label in _POSS_SURFACE_LABEL.items():
            if lower.endswith(suffix) and label == poss:
                return surface[-len(suffix):]
        if poss in {"1sg", "2sg"}:
            return surface[-2:]
        if poss in {"1pl", "2pl", "3sg", "3pl", "3sg/3pl"}:
            return surface[-3:]
        return surface[-3:]

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
