from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


LearnableType = Literal[
    "vocabulary",
    "conjugation",
    "agreement",
    "idiom",
    "grammar",
    "nuance",
]


# ── API-facing types (stable public contract) ─────────────────────────────────

class LearnableObject(BaseModel):
    id: str
    type: LearnableType
    label: str
    lesson_data: dict[str, Any] = Field(default_factory=dict)
    confidence: float | None = None


class SentenceResult(BaseModel):
    text: str
    learnable_objects: list[LearnableObject] = Field(default_factory=list)


class ParseRequest(BaseModel):
    text: str = Field(min_length=1)
    language: str = Field(min_length=2, max_length=10)
    source_url: str | None = Field(
        default=None,
        description="Optional provenance URL; stored for attribution, not fetched by the server.",
    )


class ParseResponse(BaseModel):
    sentences: list[SentenceResult]


class LessonResponse(BaseModel):
    id: str
    title: str
    content_markdown: str
    example_text: str | None = None


class ReviewRequest(BaseModel):
    object_id: str
    quality: int = Field(ge=1, le=4)
    review_state: dict[str, Any] | None = None


class ReviewResponse(BaseModel):
    object_id: str
    next_interval_days: int
    review_state: dict[str, Any]


# ── Plugin-facing types (internal; plugins return these) ──────────────────────

class RelationHint(BaseModel):
    """Directed relationship hint from a plugin candidate to another object.

    The parse route resolves both ends to canonical UUIDs and writes an
    ``ObjectRelationRow``.  If the target is not present in the current
    parse, the hint is silently skipped.
    """
    relation_type: str          # "conjugation_of" | "agreement_of" | "related_to"
    target_canonical_form: str  # canonical_form of the target object
    target_type: LearnableType  # type of the target object


class CandidateObject(BaseModel):
    """Raw extraction from a plugin before canonical-ID assignment.

    ``canonical_form`` is the stable key that uniquely identifies this
    item within its ``(language, type)`` space — e.g. the lemma for
    vocabulary, or ``{lemma}:{tense}:{mood}:{person}:{number}`` for
    conjugations.  The parse route derives the deterministic UUID from
    ``canonical_object_id(language, type, canonical_form)``.
    """
    canonical_form: str
    type: LearnableType
    label: str
    lesson_data: dict[str, Any] = Field(default_factory=dict)
    confidence: float | None = None
    relation_hints: list[RelationHint] = Field(default_factory=list)


class CandidateSentenceResult(BaseModel):
    text: str
    candidates: list[CandidateObject] = Field(default_factory=list)
