"""Multilingual text validation and normalization for Mnemosyne ingestion.

Call ``validate_ingest_text(text, language)`` before handing text to the
parse pipeline.  It returns ``(normalized_text, warnings)`` where warnings
are non-fatal cautions (e.g. probable script mismatch) intended for the
client.  Hard failures (empty text, oversized) raise ``ValueError``.
"""
from __future__ import annotations

import unicodedata
from collections import Counter

# Hard upper bound on accepted text length.
MAX_TEXT_CHARS = 50_000

# Unicode code-point ranges mapped to script-family labels.
# Only letter characters (Unicode category L*) are counted; digits,
# punctuation, and whitespace are script-neutral and ignored.
_SCRIPT_RANGES: list[tuple[int, int, str]] = [
    # Latin
    (0x0041, 0x007A, "latin"),    # Basic Latin A–Z / a–z
    (0x00C0, 0x024F, "latin"),    # Latin-1 Supplement + Extended A/B
    (0x1E00, 0x1EFF, "latin"),    # Latin Extended Additional
    # Cyrillic
    (0x0400, 0x04FF, "cyrillic"),
    # Greek
    (0x0370, 0x03FF, "greek"),
    # Hebrew
    (0x0590, 0x05FF, "hebrew"),
    # Arabic (multiple blocks)
    (0x0600, 0x06FF, "arabic"),
    (0x0750, 0x077F, "arabic"),   # Arabic Supplement
    (0xFB50, 0xFDFF, "arabic"),   # Arabic Presentation Forms-A
    (0xFE70, 0xFEFF, "arabic"),   # Arabic Presentation Forms-B
    # Devanagari
    (0x0900, 0x097F, "devanagari"),
    # Bengali
    (0x0980, 0x09FF, "bengali"),
    # Gujarati
    (0x0A80, 0x0AFF, "gujarati"),
    # Tamil
    (0x0B80, 0x0BFF, "tamil"),
    # Telugu
    (0x0C00, 0x0C7F, "telugu"),
    # Kannada
    (0x0C80, 0x0CFF, "kannada"),
    # Malayalam
    (0x0D00, 0x0D7F, "malayalam"),
    # Thai
    (0x0E00, 0x0E7F, "thai"),
    # Georgian
    (0x10A0, 0x10FF, "georgian"),
    # Hangul
    (0x1100, 0x11FF, "hangul"),
    (0xAC00, 0xD7A3, "hangul"),
    # CJK (Hiragana, Katakana, unified ideographs, extension A)
    (0x3040, 0x30FF, "cjk"),
    (0x4E00, 0x9FFF, "cjk"),
    (0x3400, 0x4DBF, "cjk"),
    (0xF900, 0xFAFF, "cjk"),
    # Ethiopic
    (0x1200, 0x137F, "ethiopic"),
    # Armenian
    (0x0530, 0x058F, "armenian"),
]

# Expected dominant script family for a BCP-47 language prefix.
# Latin-script languages are listed explicitly so that non-Latin text submitted
# under a Latin language code is caught by the script check.
_LANG_EXPECTED_SCRIPT: dict[str, str] = {
    # Latin-script languages
    "en": "latin",
    "es": "latin",
    "fr": "latin",
    "de": "latin",
    "it": "latin",
    "pt": "latin",
    "nl": "latin",
    "pl": "latin",
    "sv": "latin",
    "no": "latin",
    "da": "latin",
    "fi": "latin",
    "ro": "latin",
    "cs": "latin",
    "sk": "latin",
    "hr": "latin",
    "sl": "latin",
    "hu": "latin",
    "tr": "latin",
    "id": "latin",
    "ms": "latin",
    "vi": "latin",
    "la": "latin",
    # Non-Latin scripts
    "ar": "arabic",
    "fa": "arabic",
    "ur": "arabic",
    "he": "hebrew",
    "yi": "hebrew",
    "ru": "cyrillic",
    "uk": "cyrillic",
    "bg": "cyrillic",
    "sr": "cyrillic",
    "mk": "cyrillic",
    "el": "greek",
    "hi": "devanagari",
    "mr": "devanagari",
    "sa": "devanagari",
    "ne": "devanagari",
    "bn": "bengali",
    "gu": "gujarati",
    "ta": "tamil",
    "te": "telugu",
    "kn": "kannada",
    "ml": "malayalam",
    "th": "thai",
    "ka": "georgian",
    "ko": "hangul",
    "zh": "cjk",
    "am": "ethiopic",
    "hy": "armenian",
}


def normalize_text(text: str) -> str:
    """NFC-normalize *text* and strip leading/trailing Unicode whitespace."""
    return unicodedata.normalize("NFC", text).strip()


def detect_dominant_script(text: str) -> str | None:
    """Return the dominant script family among letter characters in *text*.

    Returns ``None`` when no recognisable letters are found (e.g. the text
    is entirely digits or punctuation).
    """
    counts: Counter[str] = Counter()
    for ch in text:
        if not unicodedata.category(ch).startswith("L"):
            continue  # skip non-letter characters
        cp = ord(ch)
        for start, end, family in _SCRIPT_RANGES:
            if start <= cp <= end:
                counts[family] += 1
                break
        # Characters outside all ranges are counted under their Unicode name
        # but we don't surface that in warnings — unknown scripts are fine.
    if not counts:
        return None
    return counts.most_common(1)[0][0]


def _detect_latin_language(text: str, declared_language: str) -> str | None:
    """Return a warning when langdetect is confident the text is a different Latin-script language.

    Only fires for Latin-script languages — non-Latin mismatches are already
    caught by the script-family check in ``validate_ingest_text``.
    Requires at least 60 characters and >= 80% confidence to avoid false positives.
    Returns ``None`` when detection is inconclusive or languages match.
    """
    if len(text) < 60:
        return None
    lang_prefix = declared_language[:2].lower()
    # Only run for Latin-script languages — non-Latin mismatches are caught by script check.
    if _LANG_EXPECTED_SCRIPT.get(lang_prefix) != "latin":
        return None
    try:
        from langdetect import detect_langs  # noqa: PLC0415
        results = detect_langs(text)
        if not results:
            return None
        top = results[0]
        if top.prob < 0.80:
            return None
        detected = top.lang.split("-")[0]  # strip region suffix (e.g. zh-cn → zh)
        if detected == lang_prefix:
            return None
        return (
            f"Text appears to be '{detected}' "
            f"({top.prob:.0%} confidence), "
            f"but '{declared_language}' was selected. "
            "Verify your language selection."
        )
    except Exception:
        return None


def validate_ingest_text(
    text: str,
    language: str,
    *,
    max_chars: int = MAX_TEXT_CHARS,
) -> tuple[str, list[str]]:
    """Normalize and validate *text* for ingestion.

    Args:
        text:      Raw input text from the client.
        language:  BCP-47 language code declared by the client.
        max_chars: Hard upper bound on the normalized character count.

    Returns:
        ``(normalized_text, warnings)`` — *warnings* are non-fatal cautions
        that should be surfaced to the user but do not block ingestion.

    Raises:
        ValueError: On hard failures (empty after normalization; too long).
    """
    normalized = normalize_text(text)

    if not normalized:
        raise ValueError("Text is empty after normalization.")

    if len(normalized) > max_chars:
        raise ValueError(
            f"Text is too long: {len(normalized):,} characters "
            f"(maximum {max_chars:,})."
        )

    warnings: list[str] = []
    detected_script = detect_dominant_script(normalized)

    if detected_script is not None:
        lang_prefix = language[:2].lower()
        expected = _LANG_EXPECTED_SCRIPT.get(lang_prefix)

        # Only warn when we have a clear expectation and the detected script
        # differs.  Skip the check for Latin because transliterated text is
        # common (e.g. romanized Japanese, Pinyin for Chinese).
        if expected is not None and detected_script != expected and detected_script != "latin":
            warnings.append(
                f"Text appears to be predominantly {detected_script} script, "
                f"but language '{language}' typically uses "
                f"{expected} script. Verify your language selection."
            )

    # Same-script language detection (e.g. French text submitted as Spanish).
    # Only runs when the script check found no issue.
    if not warnings:
        hint = _detect_latin_language(normalized, language)
        if hint:
            warnings.append(hint)

    return normalized, warnings
