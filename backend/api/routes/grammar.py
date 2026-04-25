"""Grammar rules endpoints.

GET /grammar/{language}
    ?level=B1          one CEFR level (default: all)
    ?category=verb_tenses  filter by category slug
    ?limit=50&offset=0

GET /grammar/{language}/categories
    List distinct categories present for a language.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import distinct, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db_session as get_db
from backend.models import GrammarRule

router = APIRouter(prefix="/grammar", tags=["grammar"])


class GrammarRuleOut(BaseModel):
    id: int
    language: str
    cefr_level: str
    category: str
    name: str
    description: str
    examples: list[dict]
    source: str

    model_config = {"from_attributes": True}


class CategoryOut(BaseModel):
    category: str
    count: int


@router.get("/{language}", response_model=list[GrammarRuleOut])
async def list_grammar_rules(
    language: str,
    level: Annotated[str | None, Query(description="Single CEFR level, e.g. B1")] = None,
    category: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    db: AsyncSession = Depends(get_db),
) -> list[GrammarRule]:
    stmt = select(GrammarRule).where(GrammarRule.language == language.lower())

    if level:
        stmt = stmt.where(GrammarRule.cefr_level == level.upper())
    if category:
        stmt = stmt.where(GrammarRule.category == category.lower())

    stmt = (
        stmt.order_by(GrammarRule.cefr_level, GrammarRule.category, GrammarRule.name)
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("/{language}/categories", response_model=list[str])
async def list_categories(
    language: str,
    level: Annotated[str | None, Query()] = None,
    db: AsyncSession = Depends(get_db),
) -> list[str]:
    stmt = select(distinct(GrammarRule.category)).where(GrammarRule.language == language.lower())
    if level:
        stmt = stmt.where(GrammarRule.cefr_level == level.upper())
    stmt = stmt.order_by(GrammarRule.category)
    result = await db.execute(stmt)
    return [row for (row,) in result.all()]
