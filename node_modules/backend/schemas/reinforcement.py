"""Pydantic schemas for reinforcement learning and weakness profiling."""
from __future__ import annotations

from pydantic import BaseModel, Field


class ConfusionPairOut(BaseModel):
    object_id: str
    confused_with: str
    confusion_count: int
    last_confused_at: str
    next_contrast_at: str | None = None


class ObjectReviewStatus(BaseModel):
    """Review status for a single canonical object (used in the Review tab)."""
    object_id: str
    object_type: str | None = None
    progression_stage: str = "recognition"
    mastery_score: float = 0.0
    total_reviews: int = 0
    due_at: str | None = None
    days_until_due: int | None = None
    concept_type_label: str | None = None
    stability: float | None = None
    difficulty: float | None = None
    lapses: int | None = None
    confusion_pairs: list[ConfusionPairOut] = Field(default_factory=list)


class StageDistribution(BaseModel):
    recognition: int = 0
    guided_recall: int = 0
    partial_production: int = 0
    transformation: int = 0
    free_production: int = 0
    contextual_interpretation: int = 0


class ConceptTypeAccuracy(BaseModel):
    concept_type: str
    correct_count: int
    total_reviews: int
    accuracy: float


class WeaknessProfile(BaseModel):
    """Aggregated weakness profile for a learner in one language."""
    language: str
    confusion_pairs: list[ConfusionPairOut] = Field(default_factory=list)
    stage_distribution: StageDistribution = Field(default_factory=StageDistribution)
    concept_type_accuracy: list[ConceptTypeAccuracy] = Field(default_factory=list)
    high_friction_items: list[str] = Field(default_factory=list)
    total_items: int = 0
