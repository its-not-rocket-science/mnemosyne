from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from backend.schemas.parse import SentenceResult


class SourceItem(BaseModel):
    id: str
    title: str | None = None
    language: str
    created_at: datetime
    char_count: int
    # Reading progress (from SourceProgressionRow)
    next_position: int = 0
    sentences_total: int = 0
    completion_fraction: float = 0.0
    is_complete: bool = False


class SourceListResponse(BaseModel):
    sources: list[SourceItem]


class CorpusBrowseItem(BaseModel):
    id: str
    title: str | None = None
    language: str
    content_type: str
    author: str | None = None
    char_count: int
    created_at: datetime
    # Reading progress (may be absent if user never started this document)
    next_position: int = 0
    sentences_total: int = 0
    completion_fraction: float = 0.0
    started: bool = False
    is_complete: bool = False
    # User-defined tags
    tags: list[str] = []
    # User note (freetext)
    note: str | None = None
    # Fraction of objects in this doc the user has reviewed (0–1)
    vocab_density: float = 0.0


class CorpusBrowseResponse(BaseModel):
    items: list[CorpusBrowseItem]
    total: int


class CorpusLanguageSummary(BaseModel):
    language: str
    count: int


class CorpusLanguagesResponse(BaseModel):
    languages: list[CorpusLanguageSummary]


class CorpusStats(BaseModel):
    total: int
    not_started: int
    in_progress: int
    complete: int


class TagAddRequest(BaseModel):
    tag: str = Field(min_length=1, max_length=50)

    @field_validator("tag")
    @classmethod
    def strip_tag(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("tag must not be blank")
        return v


class CorpusTagsResponse(BaseModel):
    tags: list[str]


class CorpusStudyResult(BaseModel):
    mined: int
    skipped_duplicate: int
    sentences_processed: int
    limit_reached: bool = False


class NoteUpsertRequest(BaseModel):
    text: str = Field(max_length=2000)


class NoteResponse(BaseModel):
    text: str | None


class UrlImportRequest(BaseModel):
    url: str = Field(max_length=2048)
    language: str = Field(min_length=2, max_length=10)
    title: str | None = Field(None, max_length=512)

    @field_validator("url")
    @classmethod
    def validate_http_url(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("url must not be blank")
        lower = v.lower()
        if not (lower.startswith("http://") or lower.startswith("https://")):
            raise ValueError("only http and https URLs are supported")
        return v


class UrlImportResponse(BaseModel):
    source_document_id: str
    title: str | None
    char_count: int
    truncated: bool = False
    final_url: str | None = None


class SourceDetailResponse(BaseModel):
    id: str
    title: str | None = None
    language: str
    sentences: list[SentenceResult]
