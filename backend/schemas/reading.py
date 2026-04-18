"""Schemas for the reading-progression endpoints.

GET  /reading/{source_document_id}  — current position + comprehension
PATCH /reading/{source_document_id} — advance next_position
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ReadingProgressResponse(BaseModel):
    """Current reading state for one (user, source_document) pair."""

    source_document_id: str
    next_position: int = Field(ge=0, description="Zero-based index of the next sentence to read")
    sentences_total: int = Field(ge=0, description="Total sentence count in this document")
    completion_fraction: float = Field(
        ge=0.0, le=1.0,
        description="next_position / sentences_total; 1.0 when the document is finished",
    )
    avg_comprehension: float = Field(
        ge=0.0, le=1.0,
        description=(
            "Mean mastery_score across all canonical objects encountered in this document. "
            "0.0 for a fresh document; approaches 1.0 as the learner reviews its vocabulary."
        ),
    )
    last_read_at: datetime = Field(description="UTC timestamp of the last position advance")
    is_complete: bool = Field(
        description="True when next_position >= sentences_total (document fully read)"
    )


class AdvancePositionRequest(BaseModel):
    """Body for PATCH /reading/{source_document_id}."""

    sentences_read: int = Field(
        default=1,
        ge=1,
        description="Number of sentences to mark as read; clamped to sentences_total",
    )
