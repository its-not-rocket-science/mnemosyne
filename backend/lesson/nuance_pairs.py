"""Nuance pair loader — curated minimal-pair data for meaning discrimination.

Loads ``data/nuance/{language}.json`` files and exposes them as
``NuanceSet`` / ``DiscriminationDrill`` objects for the lesson engine.

Each JSON file is a single object with a top-level ``"sets"`` list.
Files are loaded once and cached per process.

Concept → nuance_type mapping
──────────────────────────────
Plugins emit ``nuance_type`` values like ``"imperfect_aspect"`` or
``"russian_aspect"``.  ``NUANCE_TYPE_TO_CONCEPT`` maps those values to the
canonical concept IDs used in the JSON files so that ``_build_nuance()``
can look up the right set automatically.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from backend.schemas.lesson import DiscriminationDrill, NuancePair, NuanceSet

_DATA_DIR = Path(__file__).parent.parent.parent / "data" / "nuance"

# Map plugin nuance_type values → JSON concept IDs.
NUANCE_TYPE_TO_CONCEPT: dict[str, str] = {
    "imperfect_aspect":   "preterite_vs_imperfect",
    "subjunctive_mood":   "subjunctive_vs_indicative",
    "reflexive_verb":     "ser_vs_estar",
    "russian_aspect":     "perfective_vs_imperfective",
}

# Map grammar pattern_id values → JSON concept IDs.
PATTERN_TO_CONCEPT: dict[str, str] = {
    "ser_copula":          "ser_vs_estar",
    "estar_copula":        "ser_vs_estar",
    "estar_progressive":   "preterite_vs_imperfect",
}


@lru_cache(maxsize=32)
def _load_raw(language: str) -> list[dict[str, Any]]:
    path = _DATA_DIR / f"{language}.json"
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("sets", [])
    except (json.JSONDecodeError, OSError):
        return []


def get_nuance_sets(
    language: str,
    *,
    concept: str | None = None,
    cefr_level: str | None = None,
    limit: int = 4,
) -> list[NuanceSet]:
    """Return ``NuanceSet`` objects for *language*.

    Parameters
    ──────────
    concept
        Filter to this concept ID only (e.g. ``"preterite_vs_imperfect"``).
    cefr_level
        Filter to this CEFR level only.
    limit
        Maximum number of sets to return.
    """
    raw_sets = _load_raw(language)
    result: list[NuanceSet] = []
    for raw in raw_sets:
        if concept and raw.get("concept") != concept:
            continue
        if cefr_level and raw.get("cefr_level") != cefr_level:
            continue
        try:
            pairs = [NuancePair(**p) for p in (raw.get("pairs") or [])]
        except Exception:
            continue
        result.append(NuanceSet(
            concept=raw["concept"],
            title=raw["title"],
            dimension=raw["dimension"],
            description=raw["description"],
            cefr_level=raw.get("cefr_level", "B1"),
            grammar_concept=raw.get("grammar_concept"),
            pairs=pairs,
        ))
        if len(result) >= limit:
            break
    return result


def get_nuance_sets_for_type(language: str, nuance_type: str) -> list[NuanceSet]:
    """Return sets relevant to *nuance_type* as emitted by a plugin."""
    concept = NUANCE_TYPE_TO_CONCEPT.get(nuance_type)
    return get_nuance_sets(language, concept=concept) if concept else []


def get_nuance_sets_for_pattern(language: str, pattern_id: str) -> list[NuanceSet]:
    """Return sets relevant to a grammar *pattern_id*."""
    concept = PATTERN_TO_CONCEPT.get(pattern_id)
    return get_nuance_sets(language, concept=concept) if concept else []


def build_discrimination_drills(
    language: str,
    *,
    concept: str | None = None,
    nuance_type: str | None = None,
    pattern_id: str | None = None,
    pairs_per_set: int = 2,
) -> list[DiscriminationDrill]:
    """Build ``DiscriminationDrill`` objects from loaded nuance pair data.

    Accepts concept, nuance_type, or pattern_id as selectors — first
    non-None selector wins.  Returns at most ``pairs_per_set`` drills per set.
    """
    if nuance_type:
        concept = NUANCE_TYPE_TO_CONCEPT.get(nuance_type) or concept
    if pattern_id and not concept:
        concept = PATTERN_TO_CONCEPT.get(pattern_id)

    sets = get_nuance_sets(language, concept=concept)
    drills: list[DiscriminationDrill] = []
    for ns in sets:
        for pair in ns.pairs[:pairs_per_set]:
            drills.append(DiscriminationDrill(
                type="discrimination",
                concept=ns.concept,
                dimension=pair.dimension or ns.dimension,
                sentence_a=pair.sentence_a,
                sentence_b=pair.sentence_b,
                question=pair.question,
                answer=pair.answer,
                label_a=pair.label_a,
                label_b=pair.label_b,
                explanation=pair.explanation,
                cefr_level=pair.cefr_level or ns.cefr_level,
            ))
    return drills
