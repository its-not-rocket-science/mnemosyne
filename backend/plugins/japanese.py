"""Japanese language plugin — spaCy ``ja_core_news_sm`` + SudachiPy.

Registers as ``language_code = "ja"``.

─────────────────────────────────────────────────────────────────────────────
WHAT THIS PLUGIN EXTRACTS
─────────────────────────────────────────────────────────────────────────────

**Vocabulary** — content words: NOUN, PROPN, ADJ, ADV, and VERB/AUX tokens
whose VerbForm is non-finite (Part/Inf/Conv) or that have no VerbForm set.

  Skipped POS: ADP (particles), AUX (auxiliaries in finite chains), CCONJ,
  SCONJ, PUNCT, SPACE, X, SYM, INTJ, PART, PRON, NUM.

  Finite verbs (VerbForm=Fin) are also emitted as vocabulary because Japanese
  verbal morphology is carried by the auxiliary chain (ます, た, ない, …),
  not by the main verb stem.  Extracting conjugation objects for the full
  auxiliary chain is deferred.

  lesson_data keys: lemma, pos, reading (hiragana), pos_detail*,
                    confidence_note*
  (* = only when available)

**Reading (transliteration)** — the ``Reading`` morph feature from SudachiPy
is in katakana.  This plugin converts it to hiragana (subtract U+60 from
each katakana codepoint) and stores it as ``lesson_data["reading"]``.
This is exposed as ``transliteration_scheme = "hiragana"`` in capabilities.

─────────────────────────────────────────────────────────────────────────────
NOT YET IMPLEMENTED (future iterations)
─────────────────────────────────────────────────────────────────────────────

Full conjugation chain extraction (verb stem + auxiliary chain) is deferred.
Kanji reading annotation is limited to what SudachiPy provides; no additional
reading lookup.
Romaji transliteration is not provided (hiragana is preferred over romaji).
Idiom detection is deferred.

─────────────────────────────────────────────────────────────────────────────
KNOWN MODEL LIMITATIONS (ja_core_news_sm)
─────────────────────────────────────────────────────────────────────────────

- The Reading field is populated for most content words but absent for some
  rare vocabulary and all-kana words.
- Compound nouns (e.g. 東京都) may be split differently than expected.
- Proper nouns (PROPN) are included with confidence 0.60.
- The model conflates some ADJ and NOUN readings for な-adjectives; both may
  appear as NOUN with Inflection data.
"""
from __future__ import annotations

import logging
from functools import cached_property
from typing import Any

from backend.plugins.cefr_vocab import A1 as _CEFR_A1
from backend.core.vocab_index import get_cefr_level as _get_cefr_level
from backend.schemas.language import LanguageCapabilities
from backend.schemas.parse import CandidateObject, CandidateSentenceResult

logger = logging.getLogger(__name__)

_A1: frozenset[str] = _CEFR_A1.get("ja", frozenset())

# ── POS filter ────────────────────────────────────────────────────────────────

_SKIP_POS = frozenset({
    "ADP", "AUX", "CCONJ", "SCONJ", "PUNCT", "SPACE",
    "X", "SYM", "INTJ", "PART", "PRON", "NUM",
})

# ── Confidence note ───────────────────────────────────────────────────────────

_CONFIDENCE_NOTE_NO_READING = (
    "Reading unavailable for this token — SudachiPy did not provide one."
)


# ── Plugin ────────────────────────────────────────────────────────────────────

class JapanesePlugin:
    language_code = "ja"
    display_name  = "Japanese"
    direction     = "ltr"
    capabilities  = LanguageCapabilities(
        code="ja",
        display_name="Japanese",
        direction="ltr",
        script_family="cjk",
        tokenization_mode="segmented",     # SudachiPy word-boundary segmentation
        morphology_depth="shallow",
        lesson_modes_supported=["vocabulary", "dictionary"],
        # v2 fields
        analysis_depth="morphology_light",
        segmentation_quality="high",       # SudachiPy is a production-quality
                                           # segmenter; quality degrades for
                                           # rare vocabulary and neologisms.
        tokenization_quality="high",
        morphology_quality="low",          # only reading; no conjugation chain
        syntax_support=False,
        idiom_detection=False,
        tts_lang_tag="ja",
        transliteration_scheme="hiragana",
    )

    def __init__(self) -> None:
        self.lesson_store: dict[str, CandidateObject] = {}

    # ------------------------------------------------------------------
    # Model — lazy, loaded at most once per process via cached_property
    # ------------------------------------------------------------------

    @cached_property
    def _nlp(self) -> Any:
        try:
            import spacy  # noqa: PLC0415
            return spacy.load("ja_core_news_sm")
        except ImportError as exc:
            raise RuntimeError(
                "spaCy is not installed.  Run: pip install spacy"
            ) from exc
        except OSError as exc:
            raise RuntimeError(
                "spaCy model 'ja_core_news_sm' not found. "
                "Run: python -m spacy download ja_core_news_sm"
            ) from exc

    # ------------------------------------------------------------------
    # LanguagePlugin protocol
    # ------------------------------------------------------------------

    def analyze_text(self, text: str) -> list[CandidateSentenceResult]:
        """Parse full text in a single spaCy call; return one result per sentence."""
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

    def _analyze_tokens(
        self, sentence: str, tokens: list[Any]
    ) -> CandidateSentenceResult:
        seen: set[str] = set()
        candidates: list[CandidateObject] = []
        candidates.extend(self._extract_vocabulary(tokens, seen))
        return CandidateSentenceResult(text=sentence, candidates=candidates)

    def get_lesson(self, object_id: str) -> CandidateObject | None:
        return self.lesson_store.get(object_id)

    # ------------------------------------------------------------------
    # Vocabulary
    # ------------------------------------------------------------------

    def _extract_vocabulary(
        self,
        tokens: list[Any],
        seen: set[str],
    ) -> list[CandidateObject]:
        candidates: list[CandidateObject] = []
        for tok in tokens:
            if tok.pos_ in _SKIP_POS or tok.is_punct or tok.is_space:
                continue

            lemma = tok.lemma_
            if not lemma or len(lemma) < 1 or lemma in seen:
                continue
            seen.add(lemma)

            reading_kata = _morph_first(tok, "Reading")
            reading_hira = _kata_to_hira(reading_kata) if reading_kata else None

            data: dict[str, Any] = {
                "lemma": lemma,
                "pos":   tok.pos_,
            }
            if reading_hira:
                data["reading"] = reading_hira
            else:
                data["confidence_note"] = _CONFIDENCE_NOTE_NO_READING
            cefr = _get_cefr_level("ja", lemma) or ("A1" if lemma in _A1 else None)
            if cefr:
                data["cefr_level"] = cefr

            confidence = self._vocab_confidence(tok, reading_hira)
            candidates.append(CandidateObject(
                canonical_form=lemma,
                surface_form=tok.text,
                type="vocabulary",
                label=tok.text,
                lesson_data=data,
                confidence=confidence,
            ))
        return candidates

    def _vocab_confidence(self, tok: Any, reading: str | None) -> float:
        if tok.pos_ == "PROPN":
            return 0.60
        if tok.lemma_ in _A1:
            return 0.90  # known A1 word — suppress is_oov false-positive
        if reading is None:
            return 0.65
        return 0.80


# ── Module-level helpers (stateless) ─────────────────────────────────────────

def _morph_first(tok: Any, feature: str) -> str | None:
    """Return the first value for a morph feature, or None if absent."""
    values = tok.morph.get(feature)
    return values[0] if values else None


def _kata_to_hira(text: str) -> str:
    """Convert katakana characters to hiragana by subtracting U+60.

    Katakana U+30A1–U+30F6 map directly to hiragana U+3041–U+3096.
    Non-katakana characters are passed through unchanged.
    """
    return "".join(
        chr(ord(c) - 0x60) if 0x30A1 <= ord(c) <= 0x30F6 else c
        for c in text
    )


def create_plugin() -> JapanesePlugin:
    return JapanesePlugin()
