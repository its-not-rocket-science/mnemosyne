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
