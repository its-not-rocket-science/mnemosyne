"""Mandarin Chinese (Simplified) starter plugin.

Uses ``jieba`` for word segmentation and ``pypinyin`` for tone-marked pinyin
romanization.  Both dependencies are optional — the plugin degrades gracefully
when they are absent:

    jieba missing    → character-level tokenization (one character per token)
    pypinyin missing → no romanization; lessons omit the "Romanized" field

Language code: ``zh`` (ISO 639-1 / BCP-47)
Segmentation: ``tokenization_mode = "segmented"``

Honest-claims policy
────────────────────
This plugin does NOT claim:
  - morphological analysis (Chinese lacks inflection in the Latin sense)
  - POS tagging (jieba provides POS but accuracy varies; omitted here)
  - idiomatic expression detection
  - measure word / particle / classifier identification

These are documented upgrade paths, not missing features — see the
``ARCHITECTURE.md § Segmentation Languages`` section.

Data shape
──────────
Each unique segmented token produces a single ``"vocabulary"`` candidate:

    CandidateObject(
        canonical_form = "学习",   # The word — no separate lemma in Chinese
        surface_form   = "学习",
        type           = "vocabulary",
        label          = "学习",
        lesson_data    = {
            "word":   "学习",
            "pos":    "WORD",
            "pinyin": "xué xí",   # omitted when pypinyin is absent
        },
        confidence = 0.70,        # 0.40 when falling back to char-level
    )

The lesson engine's ``_build_vocabulary`` builder emits a "Romanized" field
from ``lesson_data["pinyin"]`` when present.  The modal modal tags it with
``data-layer="romanized"`` so the script-view toggle can hide/show it.
"""
from __future__ import annotations

import re

from backend.plugins.cefr_vocab import A1 as _CEFR_A1
from backend.schemas.language import LanguageCapabilities, NuanceCapabilities
from backend.schemas.parse import CandidateObject, CandidateSentenceResult

_A1: frozenset[str] = _CEFR_A1.get("zh", frozenset())

# ── Optional heavy imports ─────────────────────────────────────────────────────
# Imported at module load so the server fails fast on a mis-configured venv
# rather than raising ImportError on the first request.

try:
    import jieba                            # type: ignore[import-untyped]  # jieba ships no py.typed marker or stubs
    _HAS_JIEBA = True
except ImportError:
    _HAS_JIEBA = False

try:
    from pypinyin import lazy_pinyin, Style  # type: ignore[import-untyped]  # pypinyin ships no py.typed marker or stubs
    _HAS_PYPINYIN = True
except ImportError:
    _HAS_PYPINYIN = False


# ── Sentence splitting ─────────────────────────────────────────────────────────
# Chinese prose uses ideographic punctuation; also handle Western equivalents
# that appear in mixed text (e.g. technical writing, social media).

_SENTENCE_RE = re.compile(r"[^.!?。！？…\n]+[.!?。！？…]?")

# ── Token filtering ────────────────────────────────────────────────────────────
# Covers CJK punctuation (U+3000–U+303F), fullwidth forms (U+FF00–U+FFEF),
# general punctuation (U+2000–U+206F), and ASCII symbol ranges.
_PUNCT_RE = re.compile(
    r"^[\s"
    r"\u3000-\u303F"   # CJK symbols and punctuation
    r"\uFF00-\uFFEF"   # Halfwidth and fullwidth forms
    r"\u2000-\u206F"   # General punctuation
    r"!-/:-@\[-`{-~"  # ASCII symbols
    r"\u00B7"          # Middle dot
    r"]+$"
)


def _is_learnable(token: str) -> bool:
    """Return True when *token* is worth presenting as a learnable object."""
    stripped = token.strip()
    if not stripped:
        return False
    if _PUNCT_RE.match(stripped):
        return False
    # Skip purely numeric tokens (years, phone numbers, etc.)
    if stripped.isdigit():
        return False
    return True


def _pinyin_for(word: str) -> str | None:
    """Return tone-marked pinyin for *word*, or None when pypinyin is absent."""
    if not _HAS_PYPINYIN:
        return None
    try:
        syllables = lazy_pinyin(word, style=Style.TONE)
        return " ".join(syllables) if syllables else None
    except Exception:
        return None


def _segment(sentence: str) -> list[str]:
    """Return word-level tokens for *sentence*.

    Uses jieba when available; falls back to one character per token when it
    is not installed (e.g. in test environments without the CJK extras).
    """
    if _HAS_JIEBA:
        return list(jieba.cut(sentence))
    # Fallback: each non-whitespace character is its own token.
    # This matches tokenization_mode="character" semantics and keeps the
    # plugin loadable without the optional dependency.
    return list(sentence.replace(" ", ""))


class MandarinChinesePlugin:
    """Segmentation-first vocabulary plugin for Mandarin Chinese (Simplified).

    Proves the segmentation-language path in Mnemosyne:
      - ``tokenization_mode = "segmented"`` signals the frontend to pack pills
        without implied whitespace between tokens.
      - ``transliteration_scheme = "pinyin_tone_marks"`` enables the
        script-view toggle in both the results panel and lesson modal.
      - Lessons show tone-marked pinyin as a "Romanized" field when
        ``pypinyin`` is available.

    This is a starter-level plugin.  It does not claim POS tagging, syntax
    trees, idiom detection, or measure-word classification.  See the module
    docstring for honest-claims details.
    """

    language_code = "zh"
    display_name  = "Mandarin Chinese (Simplified)"
    direction     = "ltr"
    capabilities  = LanguageCapabilities(
        code="zh",
        display_name="Mandarin Chinese (Simplified)",
        direction="ltr",
        script_family="cjk",
        tokenization_mode="segmented",
        morphology_depth="none",
        lesson_modes_supported=["vocabulary", "dictionary"],
        # ── v2 fields ──────────────────────────────────────────────────────
        analysis_depth="dictionary",      # segmentation + token identity only
        segmentation_quality="medium",    # jieba is reliable for modern prose
        tokenization_quality="medium",
        morphology_quality="none",        # Chinese lacks Latin-style inflection
        syntax_support=False,
        idiom_detection=False,
        tts_lang_tag="zh-CN",
        transliteration_scheme="pinyin_tone_marks",
        nuance_capabilities=NuanceCapabilities(
            idioms="none",
            phrase_families="none",
            literary_references="none",
            cultural_references="none",
            etymology="none",
            formality_register="none",
            grammar_nuance="none",
            pronunciation_tts="partial",  # zh-CN TTS reliable + pinyin display
            transliteration="partial",    # pinyin_tone_marks active
            proverb_tradition="none",
            classical_or_scriptural_allusion="none",
        ),
    )

    def __init__(self) -> None:
        self.lesson_store: dict[str, CandidateObject] = {}

    # ── LanguagePlugin protocol ─────────────────────────────────────────────────

    def analyze_text(self, text: str) -> list[CandidateSentenceResult]:
        return [self.analyze_sentence(s) for s in self.split_sentences(text)]

    def split_sentences(self, text: str) -> list[str]:
        return [
            m.group(0).strip()
            for m in _SENTENCE_RE.finditer(text)
            if m.group(0).strip()
        ]

    def analyze_sentence(self, sentence: str) -> CandidateSentenceResult:
        candidates: list[CandidateObject] = []
        seen_canonical: set[str] = set()

        for token in _segment(sentence):
            if not _is_learnable(token):
                continue
            # Chinese words do not inflect; the surface form IS the canonical key.
            canonical = token
            if canonical in seen_canonical:
                continue
            seen_canonical.add(canonical)

            lesson_data: dict = {
                "lemma": canonical,
                "word":  canonical,
                "pos":   "WORD",
            }
            if pinyin := _pinyin_for(canonical):
                lesson_data["pinyin"] = pinyin
            if canonical in _A1:
                lesson_data["cefr_level"] = "A1"
            if not _HAS_JIEBA:
                lesson_data["confidence_note"] = (
                    "character-level fallback — install jieba for word-level segmentation"
                )

            candidates.append(
                CandidateObject(
                    canonical_form=canonical,
                    surface_form=canonical,
                    type="vocabulary",
                    label=canonical,
                    lesson_data=lesson_data,
                    confidence=0.70 if _HAS_JIEBA else 0.40,
                )
            )

        return CandidateSentenceResult(text=sentence, candidates=candidates)

    def get_lesson(self, object_id: str) -> CandidateObject | None:
        return self.lesson_store.get(object_id)


def create_plugin() -> MandarinChinesePlugin:
    return MandarinChinesePlugin()
