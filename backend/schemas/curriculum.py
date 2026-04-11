from __future__ import annotations

from pydantic import BaseModel, Field

from backend.difficulty.scorer import DifficultyLabel, UserLevel


class PassageSentence(BaseModel):
    """One sentence within a passage excerpt.

    Returned inside ``SentenceDifficultyItem.passage`` when the recommended
    sentence belongs to a source document.  Provides the surrounding context
    so the frontend can display a coherent passage rather than an isolated
    sentence.

    ``is_focus`` marks the sentence that was actually selected as the
    recommendation target.  Adjacent sentences (is_focus=False) are shown
    for context only and should not be individually scored in the UI.
    """
    position: int = Field(ge=0, description="Zero-based sentence index within the parsed text")
    text: str
    is_focus: bool = Field(description="True for the recommended sentence; False for context")


class SentenceDifficultyItem(BaseModel):
    """One scored sentence returned by GET /recommend or /recommend-text.

    Source context fields
    ─────────────────────
    ``source_document_id`` and ``source_title`` are populated when the
    sentence was ingested via ``POST /ingest`` (which creates a SourceDocument
    row).  Sentences ingested via the legacy ``POST /parse`` endpoint will
    have ``None`` here.

    ``passage`` carries the recommended sentence plus up to two adjacent
    sentences from the same parsed text, preserving narrative context.
    It is empty when:
      - the sentence has no SourceDocument (legacy parse)
      - the parsed text contains only one sentence
      - the DB query for adjacent sentences failed (non-fatal)
    """
    sentence_id: str
    text: str
    language: str
    difficulty: float = Field(ge=0.0, le=1.0, description="Composite difficulty 0.0–1.0")
    difficulty_label: DifficultyLabel = Field(description="easy | ideal | hard")
    unknown_ratio: float = Field(ge=0.0, le=1.0, description="Fraction of objects below mastery threshold")
    grammar_score: float = Field(ge=0.0, le=1.0, description="Conjugation/agreement density (profile-adjusted)")
    length_score: float = Field(ge=0.0, le=1.0, description="Normalised word count (profile-adjusted)")
    known_count: int = Field(ge=0, description="Objects above mastery threshold")
    unknown_count: int = Field(ge=0, description="Objects below mastery threshold")
    total_objects: int = Field(ge=0)
    # Source context — present when the sentence came from a /ingest document
    source_document_id: str | None = None
    source_title: str | None = None
    # Surrounding sentences for coherent passage display
    passage: list[PassageSentence] = Field(default_factory=list)


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
