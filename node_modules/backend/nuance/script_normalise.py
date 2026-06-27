"""Language-aware script normalisation for cultural-catalogue surface pattern matching.

For Arabic, Persian, and Hindi, identical phrases in real texts and in the
catalogue can fail to match due to script variations that are semantically
irrelevant: tashkeel/harakat diacritics, alef/ye/alef-maqsura variants,
tatweel, ta marbuta, zero-width joiners, and nukta/anusvara typing
inconsistencies. This module strips those before catalogue comparison.

This is a pre-processing step only — it does not lemmatise, stem, or
transliterate. Importable with no dependencies beyond the Python standard
library (unicodedata).
"""
from __future__ import annotations

import unicodedata

# Arabic diacritics (tashkeel) — Unicode category Mn in the Arabic block.
_TASHKEEL = set(
    "ًٌٍَُِّْ"
    "ٕٖٓٔٗ٘ٙٚ"
    "ٰٜٟٛٝٞ"
)

# Alef variants normalised to bare alef (U+0627).
_ALEF_VARIANTS = {
    "آ": "ا",  # alef with madda
    "أ": "ا",  # alef with hamza above
    "إ": "ا",  # alef with hamza below
    "ٱ": "ا",  # alef wasla
    "ٲ": "ا",  # alef with wavy hamza above
    "ٳ": "ا",  # alef with wavy hamza below
}


def _normalise_arabic(text: str) -> str:
    """Remove tashkeel, normalise alef variants, remove tatweel."""
    text = unicodedata.normalize("NFC", text)
    text = "".join(c for c in text if c not in _TASHKEEL)
    text = "".join(_ALEF_VARIANTS.get(c, c) for c in text)
    text = text.replace("ـ", "")        # tatweel / kashida
    text = text.replace("ة", "ه")  # ta marbuta -> ha
    return text


def _normalise_persian(text: str) -> str:
    """Normalise Persian-specific script variants (reuses Arabic rules for shared script features)."""
    text = unicodedata.normalize("NFC", text)
    text = _normalise_arabic(text)
    text = text.replace("ي", "ی")  # Arabic ye -> Farsi ye
    text = text.replace("ى", "ی")  # alef-maqsura -> Farsi ye
    text = text.replace("‌", "")        # zero-width non-joiner
    return text


def _normalise_hindi(text: str) -> str:
    """Normalise Hindi/Devanagari script variants."""
    text = unicodedata.normalize("NFC", text)
    text = text.replace("ँ", "ं")  # chandrabindu -> anusvara
    text = text.replace("‍", "")        # zero-width joiner
    return text


def normalise_for_matching(text: str, language: str) -> str:
    """Normalise text for surface pattern catalogue matching.

    Applies language-specific normalisation that removes semantically
    irrelevant script variation before string comparison. This is a
    pre-processing step only — it does not lemmatise, stem, or transliterate.

    Args:
        text: The raw text span to normalise.
        language: BCP-47 language code (e.g. "ar", "fa", "hi", "en").

    Returns:
        Normalised string suitable for casefold comparison against catalogue
        surface_patterns. Always returns a string; never raises.
    """
    try:
        if language in ("ar",):
            return _normalise_arabic(text).casefold()
        if language in ("fa", "ur"):
            return _normalise_persian(text).casefold()
        if language in ("hi",):
            return _normalise_hindi(text).casefold()
        return unicodedata.normalize("NFC", text).casefold()
    except Exception:
        # text itself may be malformed (e.g. None) — the docstring promises
        # this function never raises, so the fallback must not assume `text`
        # is even a string.
        try:
            return str(text).casefold()
        except Exception:
            return ""
        return text.casefold()
