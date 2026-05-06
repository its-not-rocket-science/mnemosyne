"""Shared normalization helpers for Classical Latin and Ancient Greek lookups."""
from __future__ import annotations

import unicodedata

_MACRON_TABLE = str.maketrans("āēīōūĀĒĪŌŪ", "aeiouAEIOU")


def normalize_latin(token: str) -> str:
    """Strip macrons and return lowercase ASCII for Latin lexicon lookup."""
    nfd = unicodedata.normalize("NFD", token)
    stripped = "".join(ch for ch in nfd if unicodedata.category(ch) != "Mn")
    return stripped.translate(_MACRON_TABLE).casefold()


def normalize_greek(token: str) -> str:
    """Strip polytonic diacritics and return lowercase NFC for Greek lexicon lookup.

    Uses .lower() (not .casefold()) to preserve the ς/σ distinction, matching
    the conventional Greek writing system where final sigma ς appears at word-end.
    """
    nfd = unicodedata.normalize("NFD", token)
    stripped = "".join(ch for ch in nfd if unicodedata.category(ch) != "Mn")
    return unicodedata.normalize("NFC", stripped).lower()
