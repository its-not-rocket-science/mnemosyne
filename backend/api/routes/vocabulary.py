"""Vocabulary lookup endpoints.

GET /vocabulary/{language}
    ?level=A1,B1   comma-separated CEFR levels (default: all)
    ?pos=verb      filter by part-of-speech
    ?q=run         substring search on lemma
    ?limit=100     max rows (cap 500)
    ?offset=0

GET /vocabulary/{language}/{lemma}
    All entries for this lemma (may have multiple PoS/levels).

GET /vocabulary/{language}/{lemma}/level
    Fast single-value lookup → {"lemma": "...", "cefr_level": "B1"} or 404.
    Returns the lowest (easiest) CEFR level when multiple PoS entries exist.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db_session as get_db
from backend.models import VocabularyEntry

router = APIRouter(prefix="/vocabulary", tags=["vocabulary"])

_LEVEL_ORDER = {"A1": 1, "A2": 2, "B1": 3, "B2": 4, "C1": 5, "C2": 6}


class VocabEntryOut(BaseModel):
    id: int
    language: str
    lemma: str
    pos: str | None
    cefr_level: str
    definition: str | None
    frequency_rank: int | None
    source: str

    model_config = {"from_attributes": True}


class VocabLevelOut(BaseModel):
    lemma: str
    cefr_level: str
    pos: str | None


@router.get("/{language}", response_model=list[VocabEntryOut])
async def list_vocabulary(
    language: str,
    level: Annotated[str | None, Query(description="Comma-separated CEFR levels, e.g. A1,A2")] = None,
    pos: Annotated[str | None, Query()] = None,
    q: Annotated[str | None, Query(description="Substring search on lemma")] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
    db: AsyncSession = Depends(get_db),
) -> list[VocabularyEntry]:
    stmt = select(VocabularyEntry).where(VocabularyEntry.language == language.lower())

    if level:
        levels = [lv.strip().upper() for lv in level.split(",") if lv.strip()]
        stmt = stmt.where(VocabularyEntry.cefr_level.in_(levels))
    if pos:
        stmt = stmt.where(VocabularyEntry.pos == pos.lower())
    if q:
        stmt = stmt.where(VocabularyEntry.lemma.ilike(f"%{q}%"))

    stmt = (
        stmt.order_by(VocabularyEntry.frequency_rank.nulls_last(), VocabularyEntry.lemma)
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("/{language}/{lemma}", response_model=list[VocabEntryOut])
async def get_lemma(
    language: str,
    lemma: str,
    db: AsyncSession = Depends(get_db),
) -> list[VocabularyEntry]:
    stmt = (
        select(VocabularyEntry)
        .where(
            VocabularyEntry.language == language.lower(),
            func.lower(VocabularyEntry.lemma) == lemma.lower(),
        )
        .order_by(VocabularyEntry.pos)
    )
    result = await db.execute(stmt)
    rows = list(result.scalars().all())
    if not rows:
        raise HTTPException(status_code=404, detail=f"No vocabulary entry for '{lemma}' in {language}")
    return rows


@router.get("/{language}/{lemma}/level", response_model=VocabLevelOut)
async def get_lemma_level(
    language: str,
    lemma: str,
    db: AsyncSession = Depends(get_db),
) -> VocabLevelOut:
    """Return the lowest CEFR level for a lemma (fastest lookup for annotation enrichment)."""
    stmt = (
        select(VocabularyEntry)
        .where(
            VocabularyEntry.language == language.lower(),
            func.lower(VocabularyEntry.lemma) == lemma.lower(),
        )
    )
    result = await db.execute(stmt)
    rows = list(result.scalars().all())
    if not rows:
        raise HTTPException(status_code=404, detail=f"No vocabulary entry for '{lemma}' in {language}")
    best = min(rows, key=lambda r: _LEVEL_ORDER.get(r.cefr_level, 99))
    return VocabLevelOut(lemma=best.lemma, cefr_level=best.cefr_level, pos=best.pos)
