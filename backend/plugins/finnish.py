"""Finnish plugin — full spaCy ``fi_core_news_sm`` morphological analysis.

Registers as ``language_code = "fi"``.

─────────────────────────────────────────────────────────────────────────────
WHAT THIS PLUGIN EXTRACTS
─────────────────────────────────────────────────────────────────────────────

**Vocabulary** — open-class content words (NOUN, ADJ, ADV, PROPN) and
non-finite VERB/AUX forms.

  lesson_data keys: lemma, pos, case*, number*, degree*, vowel_harmony

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
KNOWN MODEL LIMITATIONS (fi_core_news_sm)
─────────────────────────────────────────────────────────────────────────────

- Small model; lemmatization is unreliable for many inflected forms due to
  consonant gradation (k→∅, p→v, t→d).  Morphological features (case, tense,
  mood, etc.) are generally more reliable than lemmas.
- Sentence boundary detection may miss ambiguous periods (abbreviations).
- Compound-word analysis is not performed; compounds are treated as single tokens.
- No possessive suffix analysis (inner -ni/-si/-nsa/-nsä layer).
- No CEFR vocabulary tables for Finnish in this release.
"""
from __future__ import annotations

import logging
from functools import cached_property
from typing import Any

from backend.schemas.language import LanguageCapabilities, NuanceCapabilities
from backend.schemas.parse import CandidateObject, CandidateSentenceResult, RelationHint

logger = logging.getLogger(__name__)

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


# ── Helpers ───────────────────────────────────────────────────────────────────

def _morph_first(tok: Any, feature: str) -> str | None:
    vals = tok.morph.get(feature)
    return vals[0] if vals else None


def _conj_canonical_form(
    lemma: str, tense: str, mood: str, person: str, number: str, voice: str
) -> str:
    return f"{lemma}:{tense}:{mood}:{person}:{number}:{voice}"


# ── Plugin ────────────────────────────────────────────────────────────────────

class FinnishPlugin:
    """Finnish full-morphology plugin backed by ``fi_core_news_sm``."""

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
                "fi_core_news_sm: full morphological features (15 cases, tense, mood, "
                "voice, person/number). Lemmatization unreliable for some consonant-gradation "
                "forms (small model limitation). Vowel harmony annotated on all tokens."
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
        doc = self._nlp(text.strip())
        results = []
        for sent in doc.sents:
            sent_text = sent.text.strip()
            if not sent_text:
                continue
            results.append(self._analyze_tokens(sent_text, list(sent)))
        return results

    def split_sentences(self, text: str) -> list[str]:
        doc = self._nlp(text.strip())
        return [s.text.strip() for s in doc.sents if s.text.strip()]

    def analyze_sentence(self, sentence: str) -> CandidateSentenceResult:
        doc = self._nlp(sentence)
        return self._analyze_tokens(sentence, list(doc))

    def get_lesson(self, object_id: str) -> CandidateObject | None:
        return self.lesson_store.get(object_id)

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

            confidence = 0.60 if tok.pos_ == "PROPN" else 0.80
            if confidence < 0.70:
                data["confidence_note"] = (
                    "Proper noun: POS tag from fi_core_news_sm; "
                    "lemmatization and morphology less reliable for names."
                )

            candidates.append(CandidateObject(
                canonical_form=lemma,
                surface_form=tok.text,
                type="vocabulary",
                label=tok.text,
                lesson_data=data,
                confidence=confidence,
            ))
        return candidates


def create_plugin() -> FinnishPlugin:
    return FinnishPlugin()
