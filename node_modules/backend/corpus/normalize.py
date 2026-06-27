"""Corpus text normalisation — thin wrapper over the existing ingestion validator."""
from __future__ import annotations

from backend.ingestion.validator import validate_ingest_text


def normalize_corpus_text(text: str, language: str) -> tuple[str, list[str]]:
    """NFC-normalise *text* for *language* and return (normalised, warnings).

    Warnings are non-fatal notices (e.g. script mismatch) that are collected
    and reported without blocking ingestion.

    Raises:
        ValueError: if *text* is empty after normalisation.
    """
    return validate_ingest_text(text, language)
