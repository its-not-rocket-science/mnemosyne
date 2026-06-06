"""Runtime detector for generated cultural/literary/proverb/allusion catalogues."""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from backend.schemas.parse import CandidateObject

DATA_DIR = Path(__file__).resolve().parent / "data" / "cultural_references"
CASE_INSENSITIVE_LANGUAGES = frozenset({"en", "es", "fr", "de", "it", "pt", "ru", "la", "tr", "fi"})
WORD_BOUNDARY_LANGUAGES = CASE_INSENSITIVE_LANGUAGES
AMBIGUOUS_LOW_CONFIDENCE = 0.75


@dataclass(frozen=True)
class _Pattern:
    entry: dict[str, Any]
    pattern: str
    comparable: str
    length: int


def normalize_text(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def _comparable(text: str, language: str) -> str:
    text = normalize_text(text)
    if language in CASE_INSENSITIVE_LANGUAGES:
        return text.casefold()
    return text


@lru_cache(maxsize=None)
def load_catalog(language: str) -> tuple[dict[str, Any], ...]:
    path = DATA_DIR / f"{language}.json"
    if not path.exists():
        return ()
    payload = json.loads(path.read_text(encoding="utf-8"))
    return tuple(payload.get("entries", ()))


@lru_cache(maxsize=None)
def _patterns(language: str) -> tuple[_Pattern, ...]:
    pats: list[_Pattern] = []
    for entry in load_catalog(language):
        for surface in entry.get("surface_patterns", []):
            comp = _comparable(surface, language)
            pats.append(_Pattern(entry=entry, pattern=surface, comparable=comp, length=len(comp)))
    pats.sort(key=lambda p: (-p.length, p.entry.get("reference_type", ""), p.entry.get("id", ""), p.pattern))
    return tuple(pats)


def _boundary_ok(haystack: str, start: int, end: int, language: str) -> bool:
    if language not in WORD_BOUNDARY_LANGUAGES:
        return True
    before = haystack[start - 1] if start > 0 else ""
    after = haystack[end] if end < len(haystack) else ""
    return not (before.isalnum() or before == "_") and not (after.isalnum() or after == "_")


def _avoid_context(comp_sentence: str, entry: dict[str, Any], language: str) -> bool:
    return any(_comparable(avoid, language) in comp_sentence for avoid in entry.get("avoid_if", []))


def _confidence_note(entry: dict[str, Any]) -> str | None:
    notes = entry.get("notes")
    if entry.get("confidence", 1.0) <= AMBIGUOUS_LOW_CONFIDENCE:
        return notes or "Lower-confidence catalogue entry; annotate only when surrounding context supports this reference."
    return notes


def extract_cultural_references(sentence: str, language: str) -> list[CandidateObject]:
    """Return non-overlapping catalogue matches for *sentence* and *language*.

    Matching is deterministic: generated catalogue entries are loaded lazily,
    Unicode-normalised, sorted longest-first, and accepted only when they do not
    overlap an earlier longer match.
    """
    normalized = normalize_text(sentence)
    comp_sentence = _comparable(normalized, language)
    occupied: list[tuple[int, int]] = []
    out: list[CandidateObject] = []

    for pat in _patterns(language):
        if not pat.comparable or _avoid_context(comp_sentence, pat.entry, language):
            continue
        flags = re.IGNORECASE if language in CASE_INSENSITIVE_LANGUAGES else 0
        for match in re.finditer(re.escape(pat.pattern), normalized, flags):
            start, end = match.span()
            if not _boundary_ok(normalized, start, end, language):
                continue
            if any(start < used_end and end > used_start for used_start, used_end in occupied):
                continue
            surface = normalized[start:end]
            lesson_data = {
                "nuance_type": "cultural_reference",
                "reference_type": pat.entry["reference_type"],
                "canonical_reference": pat.entry["canonical_reference"],
                "source_work": pat.entry.get("source_work"),
                "source_author": pat.entry.get("source_author"),
                "explanation": pat.entry["short_explanation"],
                "surface": surface,
                "learner_level": pat.entry["learner_level"],
                "register": pat.entry.get("register"),
                "source": "generated_cultural_catalogue",
            }
            confidence_note = _confidence_note(pat.entry)
            if confidence_note:
                lesson_data["confidence_note"] = confidence_note
            out.append(
                CandidateObject(
                    canonical_form=pat.entry["canonical_form"],
                    type="nuance",
                    label=pat.entry["canonical_reference"],
                    surface_form=surface,
                    lesson_data={k: v for k, v in lesson_data.items() if v is not None},
                    confidence=float(pat.entry["confidence"]),
                )
            )
            occupied.append((start, end))
    out.sort(key=lambda c: (c.canonical_form, c.surface_form or ""))
    return out
