"""Mandarin Chinese (Simplified) plugin.

Uses ``jieba`` for word segmentation and ``pypinyin`` for tone-marked pinyin
romanization.  Both dependencies are optional — the plugin degrades gracefully
when they are absent:

    jieba missing    → character-level tokenization (one character per token)
    pypinyin missing → no romanization; lessons omit the "Romanized" field

When ``jieba`` is available, the plugin also attempts to use ``jieba.posseg``
for part-of-speech tagging.  POS quality is honest: ``analysis_depth`` is
upgraded to ``"pos_tagging"`` when posseg is available, but
``morphology_quality`` remains ``"none"`` because Chinese lacks Latin-style
inflection.

Language code: ``zh`` (ISO 639-1 / BCP-47)
Segmentation: ``tokenization_mode = "segmented"``

Honest-claims policy
────────────────────
This plugin does NOT claim:
  - morphological analysis (Chinese lacks inflection in the Latin sense)
  - syntax trees or dependency parsing
  - reliable idiom detection
  - measure-word / classifier coverage beyond the jieba ``q`` POS tag

POS accuracy via jieba.posseg is ``"medium"`` for modern Mandarin prose —
it is useful for teaching but should not be treated as ground truth.

Candidate types emitted
───────────────────────
  vocabulary       — open-class content words (NOUN, VERB, ADJ, ADV, PROPN,
                     WORD when POS unavailable)
  grammar/nuance   — aspect particles (了 过 着), structural particles
                     (的 地 得), classifiers (POS q)

Data shape — vocabulary
───────────────────────
    CandidateObject(
        canonical_form = "学习",
        type           = "vocabulary",
        lesson_data    = {
            "word":          "学习",
            "pos":           "NOUN" | "VERB" | … | "WORD",
            "pinyin":        "xué xí",   # omitted when pypinyin absent
            "tone_contours": [2, 2],     # per-syllable tone numbers 1–4 (5=neutral)
            "heteronyms":    [...],      # present only for polyphonic characters
        },
        confidence = 0.70,
    )

``tone_contours`` — list[int] length equals syllable count.  Uses pypinyin
Style.TONE3; digit 5 = neutral tone (e.g. 吗 ma).

``heteronyms`` — list[dict] present only when the word contains a character
with multiple distinct readings (e.g. 重, 行, 好).  Each entry:
    {"character": "重", "readings": [{"reading": "zhòng", ...}, ...]}

Data shape — grammar/nuance (aspect particle example)
──────────────────────────────────────────────────────
    CandidateObject(
        canonical_form = "了",
        type           = "grammar",
        lesson_data    = {
            "pattern_id": "zh.aspect_particle.le",
            "particle":   "了",
            "usage":      "completion marker",
            "contrast":   "过 marks experience; 着 marks duration",
            "pinyin":     "le",
            "concept_id": "zh.aspect_particle.le",
        },
        confidence = 0.80,
    )
"""
from __future__ import annotations

import re

from backend.plugins.cefr_vocab import A1 as _CEFR_A1, A2 as _CEFR_A2, B1 as _CEFR_B1, B2 as _CEFR_B2, C1 as _CEFR_C1, C2 as _CEFR_C2
from backend.schemas.language import LanguageCapabilities, NuanceCapabilities
from backend.schemas.parse import CandidateObject, CandidateSentenceResult

_A1: frozenset[str] = _CEFR_A1.get("zh", frozenset())
_A2: frozenset[str] = _CEFR_A2.get("zh", frozenset())
_B1: frozenset[str] = _CEFR_B1.get("zh", frozenset())
_B2: frozenset[str] = _CEFR_B2.get("zh", frozenset())
_C1: frozenset[str] = _CEFR_C1.get("zh", frozenset())
_C2: frozenset[str] = _CEFR_C2.get("zh", frozenset())

# ── Optional heavy imports ─────────────────────────────────────────────────────

try:
    import jieba                            # type: ignore[import-untyped]
    _HAS_JIEBA = True
except ImportError:
    _HAS_JIEBA = False

# jieba.posseg is a submodule of jieba — available whenever jieba is installed,
# but we import it separately so a partial install does not break the plugin.
try:
    import jieba.posseg as _posseg          # type: ignore[import-untyped]
    _HAS_POSSEG = _HAS_JIEBA
except ImportError:
    _HAS_POSSEG = False

try:
    from pypinyin import lazy_pinyin, Style  # type: ignore[import-untyped]
    _HAS_PYPINYIN = True
except ImportError:
    _HAS_PYPINYIN = False


# ── Sentence splitting ─────────────────────────────────────────────────────────

_SENTENCE_RE = re.compile(r"[^.!?。！？…\n]+[.!?。！？…]?")

# ── Token filtering ────────────────────────────────────────────────────────────

_PUNCT_RE = re.compile(
    r"^[\s"
    r"　-〿"   # CJK symbols and punctuation
    r"＀-￯"   # Halfwidth and fullwidth forms
    r" -⁯"   # General punctuation
    r"!-/:-@\[-`{-~"  # ASCII symbols
    r"·"          # Middle dot
    r"]+$"
)

# ── POS tag mapping (jieba → Mnemosyne) ───────────────────────────────────────
# jieba POS tags follow the Penn Chinese Treebank / Peking University scheme.
# Reference: https://gist.github.com/luw2007/6016931

_JIEBA_TO_POS: dict[str, str] = {
    "n":   "NOUN",
    "nr":  "PROPN",   # person name
    "ns":  "PROPN",   # place name
    "nt":  "NOUN",    # organisation name
    "nz":  "NOUN",    # other proper noun
    "v":   "VERB",
    "vn":  "NOUN",    # verbal noun
    "vd":  "VERB",
    "vg":  "VERB",
    "a":   "ADJ",
    "ad":  "ADV",     # adjectival adverb
    "ag":  "ADJ",
    "an":  "NOUN",    # adjectival noun
    "d":   "ADV",
    "r":   "PRON",
    "m":   "NUM",
    "q":   "CLASSIFIER",
    "u":   "PARTICLE",
    "ul":  "PARTICLE",
    "uz":  "PARTICLE",
    "ug":  "PARTICLE",
    "p":   "ADP",
    "c":   "CCONJ",
    "i":   "IDIOM",
    "l":   "IDIOM",
    "e":   "INTJ",
    "y":   "MODAL",
    "o":   "ONOMAT",
    "h":   "PREFIX",
    "k":   "SUFFIX",
    "f":   "NOUN",    # locality
    "s":   "NOUN",    # location
    "t":   "NOUN",    # time expression
    "g":   "WORD",    # morpheme
    "x":   "WORD",    # non-morpheme string
    "w":   "PUNCT",
    "b":   "ADJ",     # distinguishing word
    "j":   "NOUN",    # abbreviation
    "z":   "ADJ",     # status word
}

# POS values that produce vocabulary candidates worth teaching
_VOCAB_POS: frozenset[str] = frozenset(
    {"NOUN", "VERB", "ADJ", "ADV", "PROPN", "PRON", "NUM", "IDIOM", "PARTICLE", "WORD"}
)

# ── Grammar / nuance candidate definitions ────────────────────────────────────

# Aspect particles: 了 (completion), 过 (experiential), 着 (durative)
_ASPECT_PARTICLES: dict[str, dict] = {
    "了": {
        "pattern_id": "zh.aspect_particle.le",
        "particle":   "了",
        "usage":      "completion or change-of-state marker",
        "contrast":   "过 marks prior experience; 着 marks ongoing state",
        "concept_id": "zh.aspect_particle.le",
    },
    "过": {
        "pattern_id": "zh.aspect_particle.guo",
        "particle":   "过",
        "usage":      "experiential marker — action done at least once in lifetime",
        "contrast":   "了 marks completion; 着 marks ongoing state",
        "concept_id": "zh.aspect_particle.guo",
    },
    "着": {
        "pattern_id": "zh.aspect_particle.zhe",
        "particle":   "着",
        "usage":      "durative / continuous state marker",
        "contrast":   "了 marks completion; 过 marks prior experience",
        "concept_id": "zh.aspect_particle.zhe",
    },
}

# Structural particles: 的/地/得 (all pronounced "de")
_STRUCTURAL_PARTICLES: dict[str, dict] = {
    "的": {
        "pattern_id": "zh.structural_particle.de_attr",
        "particle":   "的",
        "usage":      "attributive marker — links modifier to following noun",
        "contrast":   "地 precedes verbs; 得 introduces degree complements",
        "concept_id": "zh.structural_particle.de",
    },
    "地": {
        "pattern_id": "zh.structural_particle.de_adv",
        "particle":   "地",
        "usage":      "adverbial marker — links adverb/adjective to following verb",
        "contrast":   "的 modifies nouns; 得 introduces degree complements",
        "concept_id": "zh.structural_particle.de",
    },
    "得": {
        "pattern_id": "zh.structural_particle.de_comp",
        "particle":   "得",
        "usage":      "degree/result complement marker — links verb to extent phrase",
        "contrast":   "的 modifies nouns; 地 modifies verbs as adverb",
        "concept_id": "zh.structural_particle.de",
    },
}

_ALL_GRAMMAR_PARTICLES: dict[str, dict] = {
    **_ASPECT_PARTICLES,
    **_STRUCTURAL_PARTICLES,
}


# ── Polyphonic character (heteronym) table ─────────────────────────────────────
# Characters with two or more distinct readings, each with different meaning.
# Readings use tone-marked pinyin; tone=0 means neutral/unstressed.
# Keep this list curated and conservative — only include characters where
# the reading difference is a genuine learner pitfall.

_HETERONYMS: dict[str, list[dict]] = {
    "重": [
        {"reading": "zhòng", "meaning": "heavy, weight, important", "example": "重要"},
        {"reading": "chóng", "meaning": "again, repeat, double",   "example": "重新"},
    ],
    "行": [
        {"reading": "xíng", "meaning": "walk, OK, capable",        "example": "行走"},
        {"reading": "háng", "meaning": "row, trade, profession",    "example": "银行"},
    ],
    "乐": [
        {"reading": "lè",   "meaning": "happy, joy",               "example": "快乐"},
        {"reading": "yuè",  "meaning": "music",                    "example": "音乐"},
    ],
    "长": [
        {"reading": "cháng","meaning": "long (in length)",         "example": "长度"},
        {"reading": "zhǎng","meaning": "grow, senior, chief",      "example": "成长"},
    ],
    "中": [
        {"reading": "zhōng","meaning": "middle, center, China",    "example": "中间"},
        {"reading": "zhòng","meaning": "hit (a target), suffer",   "example": "中奖"},
    ],
    "好": [
        {"reading": "hǎo",  "meaning": "good, well",               "example": "好人"},
        {"reading": "hào",  "meaning": "be fond of, enjoy",        "example": "好学"},
    ],
    "还": [
        {"reading": "hái",  "meaning": "still, also, yet",         "example": "还是"},
        {"reading": "huán", "meaning": "return, give back",        "example": "还书"},
    ],
    "得": [
        {"reading": "dé",   "meaning": "get, obtain, achieve",     "example": "得到"},
        {"reading": "děi",  "meaning": "must, have to",            "example": "得去"},
        {"reading": "de",   "meaning": "complement particle",      "example": "跑得快"},
    ],
    "数": [
        {"reading": "shù",  "meaning": "number, figure",           "example": "数字"},
        {"reading": "shǔ",  "meaning": "count, enumerate",         "example": "数数"},
    ],
    "种": [
        {"reading": "zhǒng","meaning": "type, kind, seed",         "example": "种类"},
        {"reading": "zhòng","meaning": "plant, sow",               "example": "种树"},
    ],
    "假": [
        {"reading": "jiǎ",  "meaning": "false, fake, pretend",     "example": "假装"},
        {"reading": "jià",  "meaning": "holiday, vacation",        "example": "假期"},
    ],
    "发": [
        {"reading": "fā",   "meaning": "send, emit, develop",      "example": "发送"},
        {"reading": "fà",   "meaning": "hair (on the head)",       "example": "头发"},
    ],
    "差": [
        {"reading": "chā",  "meaning": "difference, error",        "example": "差别"},
        {"reading": "chà",  "meaning": "bad, wrong, differ from",  "example": "差不多"},
        {"reading": "chāi", "meaning": "errand, assignment",       "example": "出差"},
    ],
    "朝": [
        {"reading": "cháo", "meaning": "dynasty, face toward",     "example": "朝代"},
        {"reading": "zhāo", "meaning": "morning (literary)",       "example": "朝霞"},
    ],
    "大": [
        {"reading": "dà",   "meaning": "big, large",               "example": "大小"},
        {"reading": "dài",  "meaning": "used in 大夫 (doctor)",     "example": "大夫"},
    ],
}


def _tone_contour(word: str) -> list[int] | None:
    """Return per-syllable tone numbers (1–4; 5 = neutral) for *word*.

    Uses pypinyin Style.TONE3 (tone digit appended to syllable).
    Returns None when pypinyin is absent or the word yields no syllables.
    """
    if not _HAS_PYPINYIN:
        return None
    try:
        from pypinyin import Style as _Style  # noqa: PLC0415
        syllables = lazy_pinyin(word, style=_Style.TONE3)
        tones: list[int] = []
        for syl in syllables:
            digit = next((c for c in reversed(syl) if c.isdigit()), None)
            tones.append(int(digit) if digit else 5)
        return tones if tones else None
    except Exception:
        return None


def _heteronyms_for(word: str) -> list[dict] | None:
    """Return heteronym data for any polyphonic characters found in *word*.

    Each entry names the character and lists its distinct readings so the
    learner understands that pronunciation depends on context.
    """
    result = []
    for char in word:
        if char in _HETERONYMS:
            result.append({
                "character": char,
                "readings":  _HETERONYMS[char],
            })
    return result if result else None


def _is_learnable(token: str) -> bool:
    """Return True when *token* is worth presenting as a learnable object."""
    stripped = token.strip()
    if not stripped:
        return False
    if _PUNCT_RE.match(stripped):
        return False
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
    """Return word-level tokens (no POS). Uses jieba or char-level fallback."""
    if _HAS_JIEBA:
        return list(jieba.cut(sentence))
    return list(sentence.replace(" ", ""))


def _segment_with_pos(sentence: str) -> list[tuple[str, str]]:
    """Return (token, jieba_pos_tag) pairs.

    Uses jieba.posseg when available; falls back to _segment() with
    empty-string tags when posseg is unavailable.
    """
    if _HAS_POSSEG:
        return [(pair.word, pair.flag) for pair in _posseg.cut(sentence)]
    return [(tok, "") for tok in _segment(sentence)]


class MandarinChinesePlugin:
    """Segmentation and POS-tagging plugin for Mandarin Chinese (Simplified).

    Core vocabulary path uses jieba for segmentation and pypinyin for pinyin.
    When jieba.posseg is available, POS tags are mapped to Mnemosyne labels
    and grammar/nuance candidates are emitted for particles and classifiers.

    Honest-claims boundaries:
    - ``morphology_quality = "none"`` — Chinese does not inflect.
    - ``analysis_depth`` = ``"pos_tagging"`` when posseg available, else
      ``"dictionary"``.
    - POS tagging accuracy is ``"medium"`` — useful, not ground truth.
    """

    language_code = "zh"
    display_name  = "Mandarin Chinese (Simplified)"
    direction     = "ltr"

    # "morphology_light" = POS tagging without syntax; "dictionary" = segmentation only.
    # morphology_quality stays "none" — POS tagging ≠ inflectional morphology.
    # Computed once at class definition time (module-level _HAS_POSSEG is stable).
    capabilities = LanguageCapabilities(
        code="zh",
        display_name="Mandarin Chinese (Simplified)",
        direction="ltr",
        script_family="cjk",
        tokenization_mode="segmented",
        morphology_depth="none",
        lesson_modes_supported=["vocabulary", "dictionary"],
        analysis_depth="morphology_light" if _HAS_POSSEG else "dictionary",
        segmentation_quality="medium",
        tokenization_quality="medium",
        # Chinese does not inflect like Spanish/German/Russian.  POS tagging
        # is provided by jieba but that is NOT inflectional morphology.
        morphology_quality="none",
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
            grammar_nuance="partial" if _HAS_POSSEG else "none",
            pronunciation_tts="partial",
            transliteration="partial",
            proverb_tradition="none",
            classical_or_scriptural_allusion="none",
        ),
    )

    def __init__(self) -> None:
        self.lesson_store: dict[str, CandidateObject] = {}

    # ── LanguagePlugin protocol ────────────────────────────────────────────────

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

        pairs = _segment_with_pos(sentence)

        for token, jieba_tag in pairs:
            if not _is_learnable(token):
                continue

            canonical = token

            # ── Grammar / nuance candidates ─────────────────────────────────
            if canonical in _ALL_GRAMMAR_PARTICLES:
                if canonical not in seen_canonical:
                    seen_canonical.add(canonical)
                    gram_data = dict(_ALL_GRAMMAR_PARTICLES[canonical])
                    if py := _pinyin_for(canonical):
                        gram_data["pinyin"] = py
                    candidates.append(CandidateObject(
                        canonical_form=canonical,
                        surface_form=canonical,
                        type="grammar",
                        label=canonical,
                        lesson_data=gram_data,
                        confidence=0.80,
                    ))
                continue

            # ── Classifier / measure word ────────────────────────────────────
            if jieba_tag == "q" and canonical not in seen_canonical:
                seen_canonical.add(canonical)
                gram_data: dict = {
                    "pattern_id": "zh.classifier",
                    "particle":   canonical,
                    "usage":      "classifier / measure word",
                    "concept_id": "zh.classifier",
                }
                if py := _pinyin_for(canonical):
                    gram_data["pinyin"] = py
                candidates.append(CandidateObject(
                    canonical_form=canonical,
                    surface_form=canonical,
                    type="grammar",
                    label=canonical,
                    lesson_data=gram_data,
                    confidence=0.75,
                ))
                continue

            # ── Skip punctuation and other non-content POS ───────────────────
            if jieba_tag == "w":
                continue

            if canonical in seen_canonical:
                continue
            seen_canonical.add(canonical)

            # Map jieba POS → Mnemosyne POS label
            mnemosyne_pos = _JIEBA_TO_POS.get(jieba_tag, "WORD") if jieba_tag else "WORD"

            # Only emit vocabulary for content-word POS
            if mnemosyne_pos not in _VOCAB_POS:
                continue

            lesson_data: dict = {
                "lemma": canonical,
                "word":  canonical,
                "pos":   mnemosyne_pos,
            }
            if py := _pinyin_for(canonical):
                lesson_data["pinyin"] = py
            if tc := _tone_contour(canonical):
                lesson_data["tone_contours"] = tc
            if ht := _heteronyms_for(canonical):
                lesson_data["heteronyms"] = ht
            if canonical in _A1:
                lesson_data["cefr_level"] = "A1"
            elif canonical in _A2:
                lesson_data["cefr_level"] = "A2"
            elif canonical in _B1:
                lesson_data["cefr_level"] = "B1"
            elif canonical in _B2:
                lesson_data["cefr_level"] = "B2"
            elif canonical in _C1:
                lesson_data["cefr_level"] = "C1"
            elif canonical in _C2:
                lesson_data["cefr_level"] = "C2"
            if not _HAS_JIEBA:
                lesson_data["confidence_note"] = (
                    "character-level fallback — install jieba for word-level segmentation"
                )

            candidates.append(CandidateObject(
                canonical_form=canonical,
                surface_form=canonical,
                type="vocabulary",
                label=canonical,
                lesson_data=lesson_data,
                confidence=0.70 if _HAS_JIEBA else 0.40,
            ))

        return CandidateSentenceResult(text=sentence, candidates=candidates)

    def get_lesson(self, object_id: str) -> CandidateObject | None:
        return self.lesson_store.get(object_id)


def create_plugin() -> MandarinChinesePlugin:
    return MandarinChinesePlugin()
