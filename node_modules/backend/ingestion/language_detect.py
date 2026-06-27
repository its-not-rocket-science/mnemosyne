"""Lightweight language detection without third-party ML dependencies.

Strategy
--------
1. ``detect_dominant_script`` (from ``validator``) maps unambiguously non-Latin
   scripts directly to a language code with high confidence.
2. For Latin-script text, stopword frequency scoring ranks supported language
   candidates by the fraction of sampled words that match each language's
   common function-word list.  The best match wins if it clears the minimum
   hit-rate threshold *and* its margin over the second-best is large enough to
   avoid false positives on code-switched or mixed text.

This is intentionally simple and fast.  It handles a paragraph or more of
authentic text reliably for the languages in ``_STOPWORDS``.  For ambiguous
inputs (short snippets, code, mixed-language text) it returns a low confidence
score and the caller should not apply the result automatically.
"""
from __future__ import annotations

import re

from backend.ingestion.validator import detect_dominant_script

# Public constant — callers compare their confidence against this floor.
MIN_CONFIDENCE: float = 0.35

# Text shorter than this is not reliable for detection.
MIN_TEXT_CHARS: int = 40

# Non-Latin script → (BCP-47 code, confidence).
# Confidence is below 1.0 to leave room for edge cases (e.g. Uyghur uses
# Arabic script but its language code is "ug", not "ar").
_SCRIPT_TO_LANG: dict[str, tuple[str, float]] = {
    "arabic":     ("ar", 0.90),
    "hebrew":     ("he", 0.90),
    "cjk":        ("zh", 0.85),   # most common CJK language; ja/ko also possible
    "hangul":     ("ko", 0.93),
    "cyrillic":   ("ru", 0.80),   # could be uk/bg/sr/mk; Russian is most common
    "devanagari": ("hi", 0.85),   # could be mr/ne/sa
    "thai":       ("th", 0.95),
    "greek":      ("el", 0.93),
    "georgian":   ("ka", 0.95),
    "armenian":   ("hy", 0.95),
    "ethiopic":   ("am", 0.90),
}

# Common function words for Latin-script languages.
# Chosen for high frequency AND low cross-language overlap.
# Each set has ~28 entries; this is enough to score reliably on a paragraph.
_STOPWORDS: dict[str, frozenset[str]] = {
    "es": frozenset([
        "de", "la", "el", "en", "y", "que", "los", "se", "una", "un",
        "las", "con", "por", "para", "es", "del", "al", "su", "como", "más",
        "pero", "este", "esta", "lo", "les", "nos", "sus", "era", "fue", "hay",
    ]),
    "en": frozenset([
        "the", "of", "and", "to", "in", "is", "it", "that", "for", "on",
        "was", "with", "he", "be", "at", "by", "not", "this", "are", "from",
        "or", "an", "but", "his", "they", "have", "had", "been", "which", "were",
    ]),
    "fr": frozenset([
        "de", "la", "le", "les", "un", "une", "est", "du", "et", "en",
        "des", "que", "sur", "au", "par", "ils", "il", "se", "pas", "qui",
        "ce", "son", "sa", "nous", "vous", "leur", "dans", "mais", "plus", "tout",
    ]),
    "de": frozenset([
        "die", "der", "und", "in", "den", "von", "dem", "das", "ist", "mit",
        "ich", "zu", "auf", "ein", "eine", "bei", "wie", "nicht", "auch", "als",
        "an", "es", "des", "über", "sie", "wir", "dass", "aber", "aus", "wird",
    ]),
    "it": frozenset([
        "di", "la", "il", "un", "e", "che", "in", "una", "per", "si",
        "del", "è", "con", "dei", "le", "da", "al", "non", "ho", "ha",
        "questa", "sono", "come", "ci", "più", "anche", "su", "lo", "gli", "mi",
    ]),
    "pt": frozenset([
        "de", "a", "o", "um", "que", "em", "para", "com", "uma", "os",
        "do", "da", "no", "se", "dos", "na", "por", "mais", "como", "mas",
        "não", "das", "ao", "ele", "ela", "foi", "são", "nos", "seu", "sua",
    ]),
    "nl": frozenset([
        "de", "en", "van", "het", "een", "in", "is", "dat", "op", "te",
        "zijn", "voor", "met", "aan", "door", "om", "er", "wordt", "bij", "uit",
        "ook", "niet", "worden", "nog", "meer", "over", "dan", "was", "maar",
    ]),
    "pl": frozenset([
        "w", "i", "z", "na", "do", "nie", "to", "się", "że", "jest",
        "przez", "jak", "ale", "po", "dla", "jego", "przy", "czy", "go", "co",
        "jej", "ich", "już", "tylko", "tak", "więc", "bo", "te", "ten", "tym",
    ]),
    "la": frozenset([
        "et", "in", "est", "non", "sed", "ut", "ad", "cum", "ex", "per",
        "si", "qui", "quae", "quod", "aut", "nec", "atque", "enim", "autem", "iam",
        "quid", "vel", "tam", "hoc", "haec", "hoc", "eius", "ita", "ergo",
    ]),
}

# Hit-rate thresholds for Latin-script detection.
# A hit-rate is (stopword matches) / (sampled word count).
_MIN_HIT_RATE: float = 0.06     # below this: language undetected
_STRONG_HIT_RATE: float = 0.22  # at this rate: confidence ≈ 0.92
# Minimum margin between top and second-best to avoid ambiguous calls.
_MIN_MARGIN: float = 0.025


def detect_language(text: str) -> tuple[str | None, float]:
    """Return ``(language_code, confidence)`` for *text*.

    Returns ``(None, 0.0)`` when the text is too short, no script is
    identified, or confidence falls below :data:`MIN_CONFIDENCE`.

    Confidence is a value in ``[0, 1]``; callers should treat results
    below 0.5 as weak suggestions rather than reliable classifications.

    Note: script detection runs before the length check because CJK and
    other non-Latin scripts pack significant information into few characters.
    A 20-character Chinese sentence is reliably identifiable; a 20-character
    Latin snippet is not.
    """
    # Check dominant script first — non-Latin scripts need no minimum length.
    script = detect_dominant_script(text)
    if script and script in _SCRIPT_TO_LANG:
        lang, conf = _SCRIPT_TO_LANG[script]
        return lang, conf

    # For Latin (or unrecognised) scripts, require a minimum sample length.
    if len(text) < MIN_TEXT_CHARS:
        return None, 0.0

    return _latin_detect(text)


def _latin_detect(text: str) -> tuple[str | None, float]:
    """Score *text* against all Latin-script stopword sets."""
    # Tokenise on word characters including common accented Latin letters.
    words = re.findall(r"\b[a-zA-ZÀ-öø-ÿ]{2,}\b", text.lower())
    if len(words) < 5:
        return None, 0.0

    # Sample up to 200 words for speed on long texts.
    sample = words[:200]
    sample_size = len(sample)
    sample_set  = frozenset(sample)

    scores: dict[str, float] = {}
    for lang, stopwords in _STOPWORDS.items():
        matches  = sum(1 for w in sample if w in stopwords)
        hit_rate = matches / sample_size
        if hit_rate >= _MIN_HIT_RATE:
            scores[lang] = hit_rate

    if not scores:
        return None, 0.0

    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    best_lang, best_rate = ranked[0]

    # Reject when the top-2 scores are too close — text is ambiguous.
    if len(ranked) >= 2:
        margin = best_rate - ranked[1][1]
        if margin < _MIN_MARGIN:
            return None, 0.0

    # Map hit-rate to a confidence score in [MIN_CONFIDENCE, 0.92].
    raw_conf = MIN_CONFIDENCE + (best_rate / _STRONG_HIT_RATE) * (0.92 - MIN_CONFIDENCE)
    confidence = round(min(raw_conf, 0.92), 2)

    return best_lang, confidence
