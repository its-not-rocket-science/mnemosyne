"""Korean language plugin.

NLP hierarchy (tried in order, lazy-loaded once per process):
  1. kiwipiepy  — pip install kiwipiepy  (recommended; pure-Python wheel)
  2. Heuristic  — Hangul-run whitespace tokenizer; no morphological analysis

Canonical form conventions (IMMUTABLE — first DB write is final):

  verb:{lemma}   action verb,     lemma = citation form ending in 다  e.g. verb:먹다
  adj:{lemma}    descriptive verb (형용사); conjugates like verb        e.g. adj:예쁘다
  noun:{lemma}   noun / pronoun,  bare stem without case particles     e.g. noun:학교
  adv:{lemma}    adverb,          uninflected                          e.g. adv:빨리
  word:{surface} fallback,        unanalyzed Hangul token              e.g. word:갔어요

  XSV-compound verbs: preceding NNG/XR stem + 하다
    e.g. 공부(NNG) + 하(XSV) → verb:공부하다

Why POS-prefixed canonicals (not bare lemma like Japanese):
  - Korean homograph problem: 일 is NNG "day/work" and also root of 일하다
  - noun:일  and  verb:일하다  are distinct canonical objects with no collision
  - noun: prefix prevents the same Hangul surface from shadowing verb:

Nuance canonical forms (emitted by KoreanNuanceExtractor, never by this plugin):
  nuance:ko:politeness:{register}    register ∈ {formal_polite, informal_polite,
                                                  plain_informal, plain_formal}
  nuance:ko:particle:{citation}      e.g. nuance:ko:particle:이/가
  nuance:ko:negation:{type}          type ∈ {short_an, short_mot, long_anta, long_motda}
  nuance:ko:honorific:subject_si
"""
from __future__ import annotations

import logging
import re
from typing import Any

from backend.plugins.cefr_vocab import A1 as _CEFR_A1
from backend.schemas.language import LanguageCapabilities, NuanceCapabilities
from backend.schemas.parse import CandidateObject, CandidateSentenceResult

logger = logging.getLogger(__name__)

_A1: frozenset[str] = _CEFR_A1.get("ko", frozenset())

# ── kiwipiepy tag groups ──────────────────────────────────────────────────────

_VERB_TAGS      = frozenset({"VV", "VCP", "VCN"})
_ADJ_TAG        = "VA"
_AUX_TAG        = "VX"
_NOUN_TAGS      = frozenset({"NNG", "NNB", "NR"})
_PROPN_TAG      = "NNP"
_PRON_TAG       = "NP"
_ADV_TAGS       = frozenset({"MAG", "MAJ"})
_XSV_TAG        = "XSV"
_XR_TAG         = "XR"
_NOUN_STEM_TAGS = frozenset({"NNG", "XR"})

# Tags that carry no vocabulary lesson value — skipped entirely.
_SKIP_TAGS = frozenset({
    "JKS", "JKC", "JKG", "JKO", "JKB", "JKV", "JKQ",
    "JX", "JC",
    "EP", "EF", "EC", "ETN", "ETM",
    "XPN", "XSN", "XSA", "MM",
    "SF", "SP", "SS", "SW", "SE", "SN", "SL", "SH", "SB", "SO",
    "IC",  # interjection
})

# ── Sentence splitting ────────────────────────────────────────────────────────
_SENT_RE   = re.compile(r"[^.!?\n]+[.!?\n]?")
_HANGUL_RE = re.compile(r"[가-힣]+")  # syllable block range

_CONFIDENCE_NOTE = (
    "Korean heuristic mode: kiwipiepy not installed. "
    "Canonical form is the raw surface token — morphological analysis unavailable. "
    "Install kiwipiepy for stem extraction and POS tagging."
)

# ── kiwipiepy lazy loader ─────────────────────────────────────────────────────

_SENTINEL: object = object()
_kiwi: Any = _SENTINEL


def _get_kiwi() -> Any:
    global _kiwi
    if _kiwi is not _SENTINEL:
        return _kiwi
    try:
        from kiwipiepy import Kiwi  # noqa: PLC0415
        _kiwi = Kiwi()
        logger.info("kiwipiepy loaded for Korean morphological analysis")
    except Exception:
        _kiwi = None
        logger.info("kiwipiepy unavailable — Korean plugin in heuristic mode")
    return _kiwi


# ── Plugin ────────────────────────────────────────────────────────────────────

class KoreanPlugin:
    language_code = "ko"
    display_name  = "Korean"
    direction     = "ltr"
    capabilities  = LanguageCapabilities(
        code="ko",
        display_name="Korean",
        direction="ltr",
        script_family="other",          # Hangul; no dedicated ScriptFamily literal
        tokenization_mode="whitespace", # modern Korean is word-spaced; kiwipiepy
                                        # further sub-divides into morphemes
        morphology_depth="shallow",     # stem + POS when kiwipiepy present
        lesson_modes_supported=["vocabulary", "dictionary"],
        analysis_depth="morphology_light",
        segmentation_quality="medium",  # kiwipiepy → high; heuristic → low
        tokenization_quality="medium",
        morphology_quality="low",       # POS + stem only; no full paradigm
        syntax_support=False,
        idiom_detection=False,
        tts_lang_tag="ko",
        transliteration_scheme=None,    # Revised Romanization deferred
        nuance_capabilities=NuanceCapabilities(
            idioms="none",
            phrase_families="none",
            literary_references="none",
            cultural_references="none",
            etymology="none",
            formality_register="stub",  # politeness register from sentence-final endings
            grammar_nuance="stub",      # particles, negation, subject-honorific 시
            pronunciation_tts="partial",
            transliteration="none",
            proverb_tradition="none",
            classical_or_scriptural_allusion="none",
        ),
    )

    def __init__(self) -> None:
        self.lesson_store: dict[str, CandidateObject] = {}

    # ------------------------------------------------------------------
    # LanguagePlugin protocol
    # ------------------------------------------------------------------

    def analyze_text(self, text: str) -> list[CandidateSentenceResult]:
        return [self.analyze_sentence(s) for s in self.split_sentences(text)]

    def split_sentences(self, text: str) -> list[str]:
        return [
            m.group(0).strip()
            for m in _SENT_RE.finditer(text)
            if m.group(0).strip()
        ]

    def analyze_sentence(self, sentence: str) -> CandidateSentenceResult:
        kiwi = _get_kiwi()
        if kiwi is not None:
            return self._analyze_with_kiwi(sentence, kiwi)
        return self._analyze_heuristic(sentence)

    def get_lesson(self, object_id: str) -> CandidateObject | None:
        return self.lesson_store.get(object_id)

    # ------------------------------------------------------------------
    # kiwipiepy path
    # ------------------------------------------------------------------

    def _analyze_with_kiwi(
        self, sentence: str, kiwi: Any
    ) -> CandidateSentenceResult:
        tokens = kiwi.tokenize(sentence)
        seen: set[str] = set()
        candidates: list[CandidateObject] = []
        i = 0
        while i < len(tokens):
            tok = tokens[i]
            tag = str(tok.tag)

            if tag == _XSV_TAG:
                # Compound verb: absorb preceding NNG/XR candidate into verb:{stem}하다
                if candidates and candidates[-1].lesson_data.get("_raw_tag") in _NOUN_STEM_TAGS:
                    prev = candidates.pop()
                    prev_stem = prev.lesson_data.get("lemma", prev.surface_form)
                    compound = prev_stem + "하다"
                    cf = f"verb:{compound}"
                    if cf not in seen:
                        seen.add(cf)
                        ld: dict[str, Any] = {"lemma": compound, "pos": "VERB"}
                        cefr = _cefr_for("ko", compound)
                        if cefr:
                            ld["cefr_level"] = cefr
                        candidates.append(CandidateObject(
                            canonical_form=cf,
                            surface_form=tok.form,
                            type="vocabulary",
                            label=compound,
                            lesson_data=ld,
                            confidence=0.82,
                        ))
                # If no preceding stem, skip the XSV (fallback handled by VV path)
                i += 1
                continue

            if tag in _SKIP_TAGS or tag == _AUX_TAG:
                i += 1
                continue

            cand = self._token_to_candidate(tok, tag)
            if cand is not None and cand.canonical_form not in seen:
                seen.add(cand.canonical_form)
                candidates.append(cand)
            i += 1

        # Remove internal _raw_tag keys used only during compound detection.
        for c in candidates:
            c.lesson_data.pop("_raw_tag", None)

        return CandidateSentenceResult(text=sentence, candidates=candidates)

    def _token_to_candidate(self, tok: Any, tag: str) -> CandidateObject | None:
        form = tok.form

        if tag in _VERB_TAGS:
            lemma = form + "다"
            cf = f"verb:{lemma}"
            ld: dict[str, Any] = {"lemma": lemma, "pos": "VERB", "_raw_tag": tag}
            cefr = _cefr_for("ko", lemma)
            if cefr:
                ld["cefr_level"] = cefr
            return CandidateObject(
                canonical_form=cf, surface_form=form,
                type="vocabulary", label=lemma,
                lesson_data=ld, confidence=0.82,
            )

        if tag == _ADJ_TAG:
            lemma = form + "다"
            cf = f"adj:{lemma}"
            return CandidateObject(
                canonical_form=cf, surface_form=form,
                type="vocabulary", label=lemma,
                lesson_data={"lemma": lemma, "pos": "ADJ", "_raw_tag": tag},
                confidence=0.82,
            )

        if tag in _NOUN_TAGS:
            cf = f"noun:{form}"
            ld = {"lemma": form, "pos": "NOUN", "_raw_tag": tag}
            cefr = _cefr_for("ko", form)
            if cefr:
                ld["cefr_level"] = cefr
            return CandidateObject(
                canonical_form=cf, surface_form=form,
                type="vocabulary", label=form,
                lesson_data=ld, confidence=0.80,
            )

        if tag == _PROPN_TAG:
            cf = f"noun:{form}"
            return CandidateObject(
                canonical_form=cf, surface_form=form,
                type="vocabulary", label=form,
                lesson_data={"lemma": form, "pos": "PROPN", "_raw_tag": tag},
                confidence=0.65,
            )

        if tag == _PRON_TAG:
            cf = f"noun:{form}"
            return CandidateObject(
                canonical_form=cf, surface_form=form,
                type="vocabulary", label=form,
                lesson_data={"lemma": form, "pos": "PRON", "_raw_tag": tag},
                confidence=0.75,
            )

        if tag in _ADV_TAGS:
            cf = f"adv:{form}"
            return CandidateObject(
                canonical_form=cf, surface_form=form,
                type="vocabulary", label=form,
                lesson_data={"lemma": form, "pos": "ADV", "_raw_tag": tag},
                confidence=0.75,
            )

        if tag == _XR_TAG:
            # Root morpheme — keep as potential NNG stem for XSV compound detection.
            cf = f"noun:{form}"
            return CandidateObject(
                canonical_form=cf, surface_form=form,
                type="vocabulary", label=form,
                lesson_data={"lemma": form, "pos": "NOUN", "_raw_tag": tag},
                confidence=0.55,
            )

        return None

    # ------------------------------------------------------------------
    # Heuristic fallback path
    # ------------------------------------------------------------------

    def _analyze_heuristic(self, sentence: str) -> CandidateSentenceResult:
        seen: set[str] = set()
        candidates: list[CandidateObject] = []
        for token in _HANGUL_RE.findall(sentence):
            cf = f"word:{token}"
            if cf in seen:
                continue
            seen.add(cf)
            ld: dict[str, Any] = {
                "lemma": token,
                "pos": "unknown",
                "confidence_note": _CONFIDENCE_NOTE,
            }
            cefr = _cefr_for("ko", token)
            if cefr:
                ld["cefr_level"] = cefr
            candidates.append(CandidateObject(
                canonical_form=cf,
                surface_form=token,
                type="vocabulary",
                label=token,
                lesson_data=ld,
                confidence=0.50,
            ))
        return CandidateSentenceResult(text=sentence, candidates=candidates)


# ── Module helpers ────────────────────────────────────────────────────────────

def _cefr_for(lang: str, lemma: str) -> str | None:
    from backend.core.vocab_index import get_cefr_level as _gcl  # noqa: PLC0415
    return _gcl(lang, lemma) or ("A1" if lemma in _A1 else None)


def create_plugin() -> KoreanPlugin:
    return KoreanPlugin()
