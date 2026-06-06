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

  conj:{lemma}:{tense}:{register}  conjugation pattern extracted from EP+EF morphemes
    e.g. conj:먹다:past:informal_polite

    tense values  : present | past | future
    register values: formal_polite | informal_polite | plain_informal | plain_declarative

    EP (pre-final ending) sources: 었/았 → past; 겠 → future
    EF (sentence-final ending) sources:
      ᆸ니다/습니다/ᆸ니까/습니까 → formal_polite
      어요/아요/여요            → informal_polite
      어/아/여                   → plain_informal
      다/ㄴ다/는다               → plain_declarative

  Why POS-prefixed canonicals (not bare lemma like Japanese):
  - Korean homograph problem: 일 is NNG "day/work" and also root of 일하다
  - noun:일  and  verb:일하다  are distinct canonical objects with no collision
  - noun: prefix prevents the same Hangul surface from shadowing verb:

Nuance canonical forms (emitted by KoreanNuanceExtractor):
  ko:particle:{role}              e.g. ko:particle:topic, ko:particle:subject
  ko:ending:{speech_level}        e.g. ko:ending:polite_haeyo
  ko:tense:past / ko:aspect:progressive / ko:tense:future_prospective
  ko:negation:{short,long,inability_*}
  ko:honorific:si
  ko:connective:{go,jiman,aseo_eoseo,myeon,nikka}
"""
from __future__ import annotations

import logging
import re
from typing import Any

from backend.plugins.cefr_vocab import A1 as _CEFR_A1
from backend.schemas.language import LanguageCapabilities, NuanceCapabilities
from backend.schemas.parse import CandidateObject, CandidateSentenceResult, RelationHint

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

# Tags that carry no lesson value — skipped entirely.
# EP (pre-final) and EF (sentence-final) are NOT skipped; they are handled
# explicitly in _analyze_with_kiwi for conjugation extraction.
_SKIP_TAGS = frozenset({
    "JKS", "JKC", "JKG", "JKO", "JKB", "JKV", "JKQ",
    "JX", "JC",
    "EC", "ETN", "ETM",
    "XPN", "XSN", "XSA", "MM",
    "SF", "SP", "SS", "SW", "SE", "SN", "SL", "SH", "SB", "SO",
    "IC",  # interjection
})

# ── Conjugation classification tables ────────────────────────────────────────

# Tense from pre-final ending (EP tag) morpheme forms.
_EP_TENSE: dict[str, str] = {
    "었": "past",
    "았": "past",
    "셨": "past",    # honorific past (시 + 었 contraction)
    "겠": "future",
}

# Politeness register from sentence-final ending (EF tag) morpheme forms.
_EF_REGISTER: dict[str, str] = {
    "ᆸ니다": "formal_polite",
    "습니다": "formal_polite",
    "ᆸ니까": "formal_polite",
    "습니까": "formal_polite",
    "어요":   "informal_polite",
    "아요":   "informal_polite",
    "여요":   "informal_polite",
    "어":     "plain_informal",
    "아":     "plain_informal",
    "여":     "plain_informal",
    "다":     "plain_declarative",
    "ㄴ다":   "plain_declarative",
    "는다":   "plain_declarative",
}

# ── Sentence splitting ────────────────────────────────────────────────────────
_SENT_RE   = re.compile(r"[^.!?\n]+[.!?\n]?")
_HANGUL_RE = re.compile(r"[가-힣]+")  # syllable block range

_CONFIDENCE_NOTE = (
    "Korean heuristic mode: kiwipiepy not installed. "
    "Canonical form is the raw surface token — morphological analysis unavailable. "
    "Install kiwipiepy for stem extraction and POS tagging."
)
_PROPN_NOTE = "Proper noun detected by kiwipiepy; canonical form uses raw surface token."
_XR_NOTE    = "Root morpheme (XR tag); may be a noun stem in an XSV compound — confidence capped."

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


# ── Conjugation helpers ───────────────────────────────────────────────────────

def _classify_tense(ep_forms: list[str]) -> str:
    for f in ep_forms:
        t = _EP_TENSE.get(f)
        if t:
            return t
    return "present"


def _classify_register(ef_form: str) -> str | None:
    return _EF_REGISTER.get(ef_form)


def _make_conjugation_candidate(
    verb_lemma: str,
    verb_surface: str,
    ep_forms: list[str],
    ef_form: str,
    stem_prefix: str,  # "verb" or "adj"
) -> CandidateObject | None:
    register = _classify_register(ef_form)
    if register is None:
        return None  # unclassified ending — don't emit
    tense = _classify_tense(ep_forms)
    cf = f"conj:{verb_lemma}:{tense}:{register}"
    # Morpheme-form concatenation; may differ orthographically from the surface
    # due to Korean consonant-combination rules (e.g. 가+ᆸ니다 → 갑니다).
    conjugated = verb_surface + "".join(ep_forms) + ef_form
    return CandidateObject(
        canonical_form=cf,
        surface_form=conjugated,
        type="conjugation",
        label=conjugated,
        lesson_data={
            "lemma": verb_lemma,
            "pos": "VERB" if stem_prefix == "verb" else "ADJ",
            "tense": tense,
            "register": register,
            "verb_stem": verb_surface,
            "ep_markers": list(ep_forms),
            "ef_marker": ef_form,
            "conjugated_form": conjugated,
        },
        confidence=0.85,
        relation_hints=[
            RelationHint(
                relation_type="conjugation_of",
                target_canonical_form=f"{stem_prefix}:{verb_lemma}",
                target_type="vocabulary",
            )
        ],
    )


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
        morphology_depth="shallow",     # stem + POS + conjugation when kiwipiepy present
        lesson_modes_supported=["vocabulary", "dictionary"],
        analysis_depth="morphology_light",
        segmentation_quality="medium",  # kiwipiepy → high; heuristic → low
        tokenization_quality="medium",
        morphology_quality="medium",    # stem + POS + tense/register conjugation
        syntax_support=False,
        idiom_detection=False,
        tts_lang_tag="ko",
        transliteration_scheme=None,    # Revised Romanization deferred
        nuance_capabilities=NuanceCapabilities(
            idioms="none",
            phrase_families="none",
            literary_references="partial",
            cultural_references="partial",
            etymology="none",
            formality_register="partial",  # register from sentence-final endings (EF)
            grammar_nuance="partial",      # particles, endings, tense/aspect, negation, honorifics
            pronunciation_tts="partial",
            transliteration="none",
            proverb_tradition="partial",
            classical_or_scriptural_allusion="partial",
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

        # Conjugation state: track the most recent verb/adj stem across tokens.
        # Tuple: (lemma, surface_form, stem_prefix) where stem_prefix ∈ {"verb","adj"}.
        pending_verb: tuple[str, str, str] | None = None
        pending_ep: list[str] = []

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
                    # compound is now the pending verb for conjugation
                    pending_verb = (compound, prev_stem + "하", "verb")
                    pending_ep = []
                i += 1
                continue

            # Pre-final endings: accumulate tense markers (었/았/겠 etc.)
            if tag == "EP":
                pending_ep.append(tok.form)
                i += 1
                continue

            # Sentence-final endings: emit conjugation candidate if verb pending.
            if tag == "EF":
                if pending_verb is not None:
                    lemma, surface, prefix = pending_verb
                    conj = _make_conjugation_candidate(
                        lemma, surface, pending_ep, tok.form, prefix
                    )
                    if conj is not None and conj.canonical_form not in seen:
                        seen.add(conj.canonical_form)
                        candidates.append(conj)
                pending_verb = None
                pending_ep = []
                i += 1
                continue

            if tag in _SKIP_TAGS or tag == _AUX_TAG:
                i += 1
                continue

            cand = self._token_to_candidate(tok, tag)
            if cand is not None:
                if cand.canonical_form not in seen:
                    seen.add(cand.canonical_form)
                    candidates.append(cand)
                # Always update conjugation state, even if vocab was already seen.
                if tag in _VERB_TAGS:
                    pending_verb = (tok.form + "다", tok.form, "verb")
                    pending_ep = []
                elif tag == _ADJ_TAG:
                    pending_verb = (tok.form + "다", tok.form, "adj")
                    pending_ep = []

            i += 1

        # Remove internal _raw_tag keys used only during compound detection.
        for c in candidates:
            c.lesson_data.pop("_raw_tag", None)

        candidates.extend(self._extract_nuance(sentence, tokens, candidates, seen))
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
                lesson_data={"lemma": form, "pos": "PROPN", "_raw_tag": tag,
                             "confidence_note": _PROPN_NOTE},
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
                lesson_data={"lemma": form, "pos": "NOUN", "_raw_tag": tag,
                             "confidence_note": _XR_NOTE},
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
        candidates.extend(self._extract_nuance(sentence, [], candidates, seen))
        return CandidateSentenceResult(text=sentence, candidates=candidates)

    def _extract_nuance(
        self,
        sentence: str,
        tokens: list[Any],
        candidates: list[CandidateObject],
        seen: set[str],
    ) -> list[CandidateObject]:
        from backend.nuance.ko import KoreanNuanceExtractor  # noqa: PLC0415

        nuance_candidates = KoreanNuanceExtractor().extract_nuance(
            sentence, tokens, candidates, self.language_code
        )
        out: list[CandidateObject] = []
        for cand in nuance_candidates:
            if cand.canonical_form in seen:
                continue
            seen.add(cand.canonical_form)
            out.append(cand)
        return out


# ── Module helpers ────────────────────────────────────────────────────────────

def _cefr_for(lang: str, lemma: str) -> str | None:
    from backend.core.vocab_index import get_cefr_level as _gcl  # noqa: PLC0415
    return _gcl(lang, lemma) or ("A1" if lemma in _A1 else None)


def create_plugin() -> KoreanPlugin:
    return KoreanPlugin()
