"""User and per-user language preference schemas.

LanguagePreference
──────────────────
Per-user, per-language settings that shape how Mnemosyne presents content
and which learning pathways are offered.  These are orthogonal to FSRS
knowledge state — they describe *how* to present content, not *what* the
user knows.

Design notes
────────────
show_transliteration
    Toggle romanisation for scripts the user cannot yet read natively.
    Relevant for CJK (pinyin), Arabic/Hebrew (romanisation), Japanese
    (romaji).  Default True so new users always see it; power users can
    turn it off once they can read the native script.

script_preference
    Variant when a language has multiple orthographies:
      "simplified" / "traditional"  — Mandarin Chinese
      "modern"     / "classical"    — Arabic
    None → use the plugin default.

lesson_mode_override
    Force a lesson mode for this language, overriding the plugin's richest-
    available mode.  Useful for languages the user reads but does not
    actively drill (e.g. Latin → always "dictionary") or for beginners
    who want vocabulary-only before grammar.
    None → use the plugin's richest available mode.

Upgrade path
────────────
Future per-language settings (review reminders, target-word quotas, custom
topic filters) are added as optional fields here with sensible defaults so
existing clients are unaffected.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class FsrsParams(BaseModel):
    """Current FSRS scheduling parameters for a user.

    ``desired_retention`` is the target recall probability at the scheduled
    review date.  Values < 0.90 give longer intervals (less frequent reviews);
    values > 0.90 give shorter intervals (more frequent reviews).

    When ``last_calibrated_at`` is ``None`` the value was either the factory
    default or was set manually via PATCH.
    """

    desired_retention: float = Field(
        default=0.90,
        ge=0.70,
        le=0.97,
        description="Target recall probability at scheduled review. Range [0.70, 0.97].",
    )
    last_calibrated_at: datetime | None = Field(
        default=None,
        description="Timestamp of the last successful auto-calibration run.",
    )
    reviews_used: int | None = Field(
        default=None,
        description="Number of review events consumed in the last calibration.",
    )
    calibration_rmse: float | None = Field(
        default=None,
        description="RMSE of predicted vs actual recall per bin (lower = better fit).",
    )


class FsrsParamsUpdate(BaseModel):
    """Payload for manually setting FSRS parameters."""

    desired_retention: float = Field(
        ge=0.70,
        le=0.97,
        description="New desired retention. Range [0.70, 0.97].",
    )


class LanguagePreference(BaseModel):
    """Preferences for one (user, language) pair."""

    language_code: str = Field(description="BCP-47 language code, e.g. 'zh', 'ar', 'la'")

    show_transliteration: bool = Field(
        default=True,
        description=(
            "Show transliteration / romanisation for this language. "
            "Relevant for CJK, Arabic, Hebrew, Japanese, etc."
        ),
    )
    script_preference: str | None = Field(
        default=None,
        description=(
            "Script variant preference, or None to use the plugin default. "
            "Examples: 'simplified'/'traditional' for Chinese; "
            "'modern'/'classical' for Arabic."
        ),
    )
    lesson_mode_override: str | None = Field(
        default=None,
        description=(
            "Force a specific lesson mode: 'morphology', 'vocabulary', or 'dictionary'. "
            "None means use the plugin's richest available mode."
        ),
    )


class UserPreferences(BaseModel):
    """All per-language preferences for one user."""

    user_id: str
    languages: list[LanguagePreference] = Field(
        default_factory=list,
        description="Per-language preferences; empty if no overrides have been saved.",
    )


class KnowledgeExportItem(BaseModel):
    """FSRS state for one (user, object) pair, enriched with canonical metadata."""

    object_id: str
    language: str | None
    canonical_form: str | None = Field(
        default=None,
        description="canonical_form from canonical_objects; None when the object row is absent.",
    )
    type: str | None = Field(
        default=None,
        description="Object type (vocabulary, conjugation, …); None when object row is absent.",
    )
    display_label: str | None = Field(
        default=None,
        description="Human-readable label; None when object row is absent.",
    )
    fsrs_state: dict | None
    mastery_score: float
    first_seen: datetime | None
    last_seen: datetime
    total_reviews: int
    due_at: datetime


class UserExport(BaseModel):
    """Complete portable export of one user's knowledge state.

    Intended for data portability: a user can download this and re-import
    it into another Mnemosyne instance (import endpoint not yet implemented).

    schema_version
        Bumped whenever the structure changes in a backwards-incompatible way,
        so importers can detect format mismatches early.
    """

    schema_version: str = Field(default="1", description="Export format version.")
    exported_at: datetime
    user_id: str
    knowledge: list[KnowledgeExportItem] = Field(default_factory=list)
    language_preferences: list[LanguagePreference] = Field(default_factory=list)
