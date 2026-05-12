from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class TermProgressOut(BaseModel):
    term: str
    lemma: str | None = None
    language: str
    first_seen: datetime
    last_seen: datetime
    exposure_count: int
    review_count: int
    correct_count: int
    incorrect_count: int
    mastery_score: float
    next_review_at: datetime | None = None
    review_bucket: str
    source_lesson_ids: list[str] = Field(default_factory=list)


class TermProgressUpsert(BaseModel):
    term: str
    lemma: str | None = None
    language: str
    seen: bool = True
    reviewed: bool = False
    correct: bool | None = None
    mastery_delta: float = 0.0
    next_review_at: datetime | None = None
    source_lesson_id: str | None = None
