from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from backend.schemas.parse import SentenceResult


class SourceItem(BaseModel):
    id: str
    title: str | None = None
    language: str
    created_at: datetime
    char_count: int


class SourceListResponse(BaseModel):
    sources: list[SourceItem]


class SourceDetailResponse(BaseModel):
    id: str
    title: str | None = None
    language: str
    sentences: list[SentenceResult]
