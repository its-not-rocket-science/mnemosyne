from __future__ import annotations

from pydantic import BaseModel, Field

from backend.difficulty.scorer import DifficultyLabel, UserLevel


class SentenceDifficultyItem(BaseModel):
    """One scored sentence returned by GET /recommend or /recommend-text."""
    sentence_id: str
    text: str
    language: str
    difficulty: float = Field(ge=0.0, le=1.0, description="Composite difficulty 0.0–1.0")
    difficulty_label: DifficultyLabel = Field(description="easy | ideal | hard")
    unknown_ratio: float = Field(ge=0.0, le=1.0, description="Fraction of objects below mastery threshold")
    grammar_score: float = Field(ge=0.0, le=1.0, description="Conjugation/agreement density")
    length_score: float = Field(ge=0.0, le=1.0, description="Normalised word count")
    known_count: int = Field(ge=0, description="Objects above mastery threshold")
    unknown_count: int = Field(ge=0, description="Objects below mastery threshold")
    total_objects: int = Field(ge=0)


class RecommendTextResponse(BaseModel):
    """Response from GET /recommend-text.

    ``sentences`` are ordered by closeness to the centre of the target
    difficulty window.  An empty list means no stored sentences match the
    language and no fallback sentences exist.

    ``user_level`` encodes the user's current proficiency tier:
      beginner     < 5 items mastered
      elementary   5–19 items mastered
      intermediate 20–59 items mastered
      advanced     ≥ 60 items mastered

    ``total_mastered`` / ``total_seen`` give the raw counts that drive the
    window and level calculation.
    """
    sentences: list[SentenceDifficultyItem]
    target_difficulty_min: float = Field(ge=0.0, le=1.0)
    target_difficulty_max: float = Field(ge=0.0, le=1.0)
    user_level: UserLevel
    total_mastered: int = Field(ge=0)
    total_seen: int = Field(ge=0)
