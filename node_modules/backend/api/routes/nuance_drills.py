"""GET /nuance-drills — discrimination drills derived from nuance types found in a corpus doc.

Used by the "Practice confusables" reader action: the client collects
nuance_type values from the currently-loaded sentences and requests up to
``limit`` discrimination drills for those types.

No DB access required — drills are built from the static data/nuance/ JSON files.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from backend.api.dependencies import get_current_user
from backend.lesson.nuance_pairs import NUANCE_TYPE_TO_CONCEPT, build_discrimination_drills
from backend.schemas.lesson import DiscriminationDrill

router = APIRouter(tags=["nuance"])


class NuanceDrillsResponse:
    pass


@router.get("/nuance-drills")
async def get_nuance_drills(
    language: str = Query(..., min_length=2, max_length=10),
    nuance_types: str = Query(default="", description="Comma-separated nuance_type values"),
    limit: int = Query(default=6, ge=1, le=20),
    _current_user: str = Depends(get_current_user),
) -> dict:
    """Return discrimination drills for the requested nuance types.

    Deduplicates by concept so the same contrast pair is not repeated even
    if multiple nuance_type values map to the same concept.
    """
    types = [t.strip() for t in nuance_types.split(",") if t.strip()]
    drills: list[DiscriminationDrill] = []
    seen_concepts: set[str] = set()

    for nuance_type in types:
        if nuance_type not in NUANCE_TYPE_TO_CONCEPT:
            continue
        for drill in build_discrimination_drills(language, nuance_type=nuance_type):
            if drill.concept in seen_concepts:
                continue
            seen_concepts.add(drill.concept)
            drills.append(drill)
            if len(drills) >= limit:
                break
        if len(drills) >= limit:
            break

    return {
        "drills": [d.model_dump() for d in drills],
        "count": len(drills),
        "nuance_types_requested": types,
    }
