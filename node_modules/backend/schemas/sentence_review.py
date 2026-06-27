"""Pydantic schemas for sentence-level spaced-retrieval review items."""
from __future__ import annotations

from pydantic import BaseModel, Field


class SentenceReviewItem(BaseModel):
    """One mined review item with its sentence context and user progress."""

    id: str
    sentence_id: str
    sentence_text: str

    language: str

    #: "cloze" | "chunk_recall" | "grammar_transform" | "meaning_discrimination"
    item_type: str

    #: Prompt as displayed to the learner (may contain the blanked sentence,
    #: a transform instruction, or a discrimination question).
    prompt: str

    #: The word / phrase targeted by this item.
    target_span: str

    #: Expected answer (or self-grading reference for transform items).
    answer: str

    #: Distractor options for discrimination items.
    distractors: list[str] = Field(default_factory=list)

    #: Optional hint shown to the learner before / after answering.
    hint: str | None = None

    #: Grammar concept tag (e.g. "preterite_imperfect", "ser_estar").
    grammar_concept: str | None = None

    cefr_level: str | None = None
    difficulty_score: float | None = None

    # ── User-specific progress fields ────────────────────────────────────────
    total_reviews: int = 0
    mastery_score: float = 0.0
    streak: int = 0
    due_at: str | None = None


class SentenceContextResponse(BaseModel):
    """Surrounding sentences for a review item."""
    before: list[str]
    target: str
    after: list[str]
    source_title: str | None = None


class ReviewItemSubmitRequest(BaseModel):
    """Quality rating for a completed sentence review item."""

    #: 1 = Again, 2 = Hard, 3 = Good, 4 = Easy.
    quality: int = Field(ge=1, le=4)


class ReviewItemSubmitResponse(BaseModel):
    """Result returned after submitting a sentence review item rating."""

    item_id: str
    next_interval_days: int
    mastery_score: float
    mastery_score_before: float
    next_review_at: str
    streak: int
    total_reviews: int


class MineResult(BaseModel):
    """Summary returned by POST /review/sentence-items/mine."""

    mined: int
    skipped_duplicate: int
    sentences_processed: int


class ReviewQueueStats(BaseModel):
    """Current state of the sentence review queue for one user."""

    due_now: int
    total_items: int
    per_type: dict[str, int] = Field(default_factory=dict)
    per_language: dict[str, int] = Field(default_factory=dict)
