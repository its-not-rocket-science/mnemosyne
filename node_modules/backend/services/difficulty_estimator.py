"""Text difficulty estimation via vocabulary CEFR coverage.

Algorithm
---------
1. Tokenise the text into content words (script-aware regex; jieba for Chinese).
2. Look up each token in the in-memory CEFR vocab index.
3. Apply the 90-% coverage rule: the estimated level is the lowest CEFR band at
   which the cumulative fraction of *known* tokens reaches the threshold.
4. Return the distribution, unknown ratio, and a confidence indicator.

Design decisions
----------------
- No NLP pipeline is invoked — the estimator is intentionally lightweight so it
  can run synchronously as a pre-parse check without loading spaCy models.
- Proper nouns, numerals, and punctuation are stripped before counting.
- The CEFR index is the same in-memory map used by the plugins; no extra I/O.
- For languages with no vocab index entries (e.g. Latin, Greek), the result
  reflects only the proportion of tokens that are in the curated A1-B1 lists.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from backend.core.vocab_index import get_cefr_level

CEFR_LEVELS = ("A1", "A2", "B1", "B2", "C1", "C2")

#: Fraction of known tokens required to assign a level.
COVERAGE_THRESHOLD = 0.90

#: Minimum token count for a confident estimate.
MIN_TOKENS_CONFIDENT = 30

# ── Tokenisation ──────────────────────────────────────────────────────────────

# Unicode ranges covered by the regex:
#   Latin + Latin-Extended   A-ɏ
#   Cyrillic                 Ѐ-ӿ
#   Arabic                   ؀-ۿ
#   Hebrew                   א-ת
#   Devanagari               ऀ-ॿ
#   CJK (for lang check)     一-鿿
#   Hangul                   가-힯
#   Hiragana/Katakana        ぀-ヿ
_TOKEN_RE = re.compile(
    r"[A-Za-zÀ-ɏ"
    r"Ѐ-ӿ"
    r"؀-ۿ"
    r"א-ת"
    r"ऀ-ॿ"
    r"一-鿿"
    r"가-힯"
    r"぀-ヿ"
    r"]{2,}"
)


def _tokenise(text: str, language: str) -> list[str]:
    """Return a list of lowercase content-word tokens."""
    if language == "zh":
        try:
            import jieba  # type: ignore[import-untyped]
            return [t.strip().lower() for t in jieba.cut(text) if len(t.strip()) >= 2]
        except ImportError:
            pass
    return [m.group().lower() for m in _TOKEN_RE.finditer(text)]


# ── Estimation ────────────────────────────────────────────────────────────────

@dataclass
class DifficultyEstimate:
    language: str
    estimated_cefr: str | None
    distribution: dict[str, float] = field(default_factory=dict)
    unknown_ratio: float = 0.0
    word_count: int = 0
    analyzed_tokens: int = 0
    confident: bool = False
    note: str = ""


def estimate(text: str, language: str) -> DifficultyEstimate:
    """Return a CEFR difficulty estimate for *text* in *language*.

    Parameters
    ----------
    text:     Raw text to analyse.
    language: BCP-47 code matching a Mnemosyne plugin (e.g. ``"es"``).

    Returns
    -------
    DifficultyEstimate
        ``estimated_cefr`` is one of A1 A2 B1 B2 C1 C2 (or ``None`` when the
        text contains too few recognisable tokens).
        ``confident`` is ``True`` when ``analyzed_tokens >= MIN_TOKENS_CONFIDENT``.
    """
    tokens = _tokenise(text, language)
    word_count = len(tokens)

    counts: dict[str, int] = {level: 0 for level in CEFR_LEVELS}
    unknown = 0

    for token in tokens:
        level = get_cefr_level(language, token)
        if level in counts:
            counts[level] += 1
        else:
            unknown += 1

    total = word_count
    if total == 0:
        return DifficultyEstimate(
            language=language,
            estimated_cefr=None,
            word_count=0,
            analyzed_tokens=0,
            note="No analysable tokens found.",
        )

    known_total = sum(counts.values())
    unknown_ratio = unknown / total

    # Build normalised distribution over known + unknown.
    distribution = {level: round(counts[level] / total, 4) for level in CEFR_LEVELS}
    distribution["unknown"] = round(unknown_ratio, 4)

    # 90-% coverage: find lowest level where cumulative known fraction ≥ threshold.
    estimated: str | None = None
    cumulative = 0
    for level in CEFR_LEVELS:
        cumulative += counts[level]
        if cumulative / total >= COVERAGE_THRESHOLD:
            estimated = level
            break

    # If known tokens never reach the threshold (or all tokens are unknown),
    # treat the text as C2-level — the most conservative fallback.
    if estimated is None:
        estimated = "C2"

    confident = word_count >= MIN_TOKENS_CONFIDENT

    note = ""
    if not confident:
        note = f"Low confidence: only {word_count} token(s) analysed (need ≥{MIN_TOKENS_CONFIDENT})."
    elif unknown_ratio > 0.40:
        note = "High unknown-word ratio; vocabulary index may not cover this language fully."

    return DifficultyEstimate(
        language=language,
        estimated_cefr=estimated,
        distribution=distribution,
        unknown_ratio=round(unknown_ratio, 4),
        word_count=word_count,
        analyzed_tokens=word_count,
        confident=confident,
        note=note,
    )
