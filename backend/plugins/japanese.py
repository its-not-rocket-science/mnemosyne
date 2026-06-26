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

  lesson_data keys: lemma, pos, reading (hiragana), pitch_accent*,
                    pos_detail*, confidence_note*
  (* = only when available)

**Reading (transliteration)** — the ``Reading`` morph feature from SudachiPy
is in katakana.  This plugin converts it to hiragana (subtract U+60 from
each katakana codepoint) and stores it as ``lesson_data["reading"]``.
This is exposed as ``transliteration_scheme = "hiragana"`` in capabilities.

**Pitch accent** — a curated table of ~60 high-frequency lemmas maps each to
its NHK standard Tokyo accent number (drop_mora) and pattern label:
  drop_mora = 0  →  heiban   (平板型): LH…H — no drop within the word
  drop_mora = 1  →  atamadaka (頭高型): HL…L — drops after first mora
  drop_mora = N  →  nakadaka (中高型): LH…HLL — drops after mora N (N < end)
  drop_mora = N  →  odaka    (尾高型): LH…H+drop before particle

Coverage is limited to the curated table; unlisted lemmas carry no pitch data.
Minimal pairs (e.g. 橋 vs 箸, 雨 vs 飴, 花 vs 鼻) are annotated with a note.

─────────────────────────────────────────────────────────────────────────────
NOT YET IMPLEMENTED (future iterations)
─────────────────────────────────────────────────────────────────────────────

Full conjugation chain extraction (verb stem + auxiliary chain) is deferred.
Kanji reading annotation is limited to what SudachiPy provides; no additional
reading lookup.
Romaji transliteration is not provided (hiragana is preferred over romaji).
Idiom detection is deferred.
Pitch accent coverage beyond the curated table is deferred (would require a
full pitch-accent lexicon such as the OJAD or NHK dictionary dataset).

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

from backend.plugins.cefr_vocab import A1 as _CEFR_A1, A2 as _CEFR_A2, B1 as _CEFR_B1, B2 as _CEFR_B2, C1 as _CEFR_C1, C2 as _CEFR_C2
from backend.core.vocab_index import get_cefr_level as _get_cefr_level
from backend.schemas.language import LanguageCapabilities, NuanceCapabilities
from backend.schemas.parse import CandidateObject, CandidateSentenceResult

logger = logging.getLogger(__name__)

_A1: frozenset[str] = _CEFR_A1.get("ja", frozenset())
_A2: frozenset[str] = _CEFR_A2.get("ja", frozenset())
_B1: frozenset[str] = _CEFR_B1.get("ja", frozenset())
_B2: frozenset[str] = _CEFR_B2.get("ja", frozenset())
_C1: frozenset[str] = _CEFR_C1.get("ja", frozenset())
_C2: frozenset[str] = _CEFR_C2.get("ja", frozenset())

# ── Pitch accent — curated NHK standard Tokyo accent (drop_mora, pattern, note)
# drop_mora: NHK accent number. 0 = heiban (flat), 1+ = mora after which pitch
# drops.  pattern: one of heiban / atamadaka / nakadaka / odaka.
# Source: NHK日本語発音アクセント辞典 (standard entries only; contested readings omitted).
# ──────────────────────────────────────────────────────────────────────────────

_PITCH_ACCENT: dict[str, tuple[int, str, str]] = {
    # ── Classic minimal pairs (highest pedagogical value) ────────────────────
    "橋": (0, "heiban",    "Minimal pair: 橋(bridge)=heiban ≠ 箸(chopsticks)=atamadaka"),
    "箸": (1, "atamadaka", "Minimal pair: 箸(chopsticks)=atamadaka ≠ 橋(bridge)=heiban"),
    "雨": (1, "atamadaka", "Minimal pair: 雨(rain)=atamadaka ≠ 飴(candy)=heiban"),
    "飴": (0, "heiban",    "Minimal pair: 飴(candy)=heiban ≠ 雨(rain)=atamadaka"),
    "花": (2, "odaka",     "Minimal pair: 花(flower)=odaka ≠ 鼻(nose)=heiban"),
    "鼻": (0, "heiban",    "Minimal pair: 鼻(nose)=heiban ≠ 花(flower)=odaka"),
    "神": (1, "atamadaka", "Minimal pair: 神(god)=atamadaka ≠ 紙/髪(paper/hair)=odaka"),
    "紙": (2, "odaka",     "Minimal pair: 紙(paper)=odaka ≠ 神(god)=atamadaka; same pattern as 髪"),
    "髪": (2, "odaka",     "Minimal pair: 髪(hair)=odaka ≠ 神(god)=atamadaka; same pattern as 紙"),
    "端": (2, "odaka",     "Minimal pair: 端(edge)=odaka; cf. 橋(bridge)=heiban, 箸(chopsticks)=atamadaka"),
    # ── Nature / environment ─────────────────────────────────────────────────
    "山": (0, "heiban",    ""),
    "川": (1, "atamadaka", ""),
    "海": (2, "odaka",     ""),
    "空": (1, "atamadaka", ""),
    "風": (0, "heiban",    ""),
    "水": (0, "heiban",    ""),
    "火": (1, "atamadaka", ""),
    "土": (2, "odaka",     ""),
    "石": (0, "heiban",    ""),
    "雪": (2, "odaka",     ""),
    "雲": (2, "odaka",     ""),
    "声": (0, "heiban",    ""),
    "光": (3, "nakadaka",  ""),
    # ── Seasons ──────────────────────────────────────────────────────────────
    "春": (0, "heiban",    "Season: spring (heiban)"),
    "夏": (2, "odaka",     "Season: summer (odaka)"),
    "秋": (2, "odaka",     "Season: autumn (odaka)"),
    "冬": (0, "heiban",    "Season: winter (heiban); minimal pair in pattern with 春"),
    # ── Animals ──────────────────────────────────────────────────────────────
    "猫": (1, "atamadaka", ""),
    "犬": (2, "odaka",     ""),
    "魚": (0, "heiban",    ""),
    "鳥": (1, "atamadaka", ""),
    "馬": (2, "odaka",     ""),
    # ── Body ─────────────────────────────────────────────────────────────────
    "目": (1, "atamadaka", "1-mora word; becomes HL before particle"),
    "手": (1, "atamadaka", "1-mora word"),
    "足": (0, "heiban",    ""),
    "頭": (3, "odaka",     ""),
    "顔": (3, "nakadaka",  ""),
    "心": (4, "odaka",     ""),
    # ── Common nouns ─────────────────────────────────────────────────────────
    "本": (1, "atamadaka", ""),
    "今": (2, "odaka",     ""),
    "名前": (3, "odaka",   ""),
    "言葉": (3, "odaka",   ""),
    "力": (3, "odaka",     ""),
    "桜": (3, "odaka",     ""),
    "新聞": (0, "heiban",  ""),
    "学校": (0, "heiban",  ""),
    "先生": (3, "nakadaka",""),
    "友達": (0, "heiban",  ""),
    "電車": (0, "heiban",  ""),
    "仕事": (2, "nakadaka",""),
    "時間": (0, "heiban",  ""),
    # ── Common verbs (dictionary form) ───────────────────────────────────────
    "見る": (1, "atamadaka", ""),
    "行く": (0, "heiban",    ""),
    "食べる": (2, "nakadaka",""),
    "飲む": (2, "odaka",     ""),
    "書く": (0, "heiban",    ""),
    "読む": (2, "odaka",     ""),
    "来る": (1, "atamadaka", ""),
    "話す": (0, "heiban",    ""),
    "聞く": (0, "heiban",    ""),
}


def _pitch_accent_entry(lemma: str) -> dict | None:
    """Return pitch_accent lesson_data dict for lemma, or None if not in table."""
    entry = _PITCH_ACCENT.get(lemma)
    if entry is None:
        return None
    drop_mora, pattern, note = entry
    result: dict = {"drop_mora": drop_mora, "pattern": pattern}
    if note:
        result["note"] = note
    return result


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
        analysis_depth="full",            # spaCy POS/lemma + nuance (keigo/particles/yojijukugo)
        segmentation_quality="high",       # SudachiPy is a production-quality
                                           # segmenter; quality degrades for
                                           # rare vocabulary and neologisms.
        tokenization_quality="high",
        morphology_quality="low",          # only reading; no conjugation chain
        syntax_support=False,
        idiom_detection=False,
        tts_lang_tag="ja",
        transliteration_scheme="hiragana",
        nuance_capabilities=NuanceCapabilities(
            idioms="none",
            phrase_families="none",
            literary_references="partial",
            cultural_references="partial",
            etymology="none",
            formality_register="partial",  # keigo: sonkeigo / kenjōgo / teineigo
            grammar_nuance="partial",     # particles, keigo, verbal government, yojijukugo
            pronunciation_tts="partial",  # ja TTS reliable + hiragana reading
            transliteration="stub",       # hiragana reading only; no full romaji
            proverb_tradition="partial",
            classical_or_scriptural_allusion="partial",
        ),
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
        candidates.extend(self._extract_nuance(sentence, tokens, candidates, seen))
        return CandidateSentenceResult(text=sentence, candidates=candidates)

    def _extract_nuance(
        self,
        sentence: str,
        tokens: list[Any],
        candidates: list[CandidateObject],
        seen: set[str],
    ) -> list[CandidateObject]:
        from backend.nuance.ja import JapaneseNuanceExtractor  # noqa: PLC0415

        nuance_candidates = JapaneseNuanceExtractor().extract_nuance(
            sentence, tokens, candidates, self.language_code
        )
        out: list[CandidateObject] = []
        for cand in nuance_candidates:
            if cand.canonical_form in seen:
                continue
            seen.add(cand.canonical_form)
            out.append(cand)
        return out

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
            if tok.pos_ == "PROPN":
                data["confidence_note"] = "proper noun — may not generalise to common vocabulary"
            if reading_hira:
                data["reading"] = reading_hira
            elif "confidence_note" not in data:
                data["confidence_note"] = _CONFIDENCE_NOTE_NO_READING
            pa = _pitch_accent_entry(lemma)
            if pa is not None:
                data["pitch_accent"] = pa
            cefr = _get_cefr_level("ja", lemma) or ("A1" if lemma in _A1 else "A2" if lemma in _A2 else "B1" if lemma in _B1 else "B2" if lemma in _B2 else "C1" if lemma in _C1 else "C2" if lemma in _C2 else None)
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
        if tok.lemma_ in _A2:
            return 0.88  # known A2 word
        if tok.lemma_ in _B1:
            return 0.86  # known B1 word
        if tok.lemma_ in _B2:
            return 0.84
        if tok.lemma_ in _C1:
            return 0.82
        if tok.lemma_ in _C2:
            return 0.80
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
