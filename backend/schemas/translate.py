from __future__ import annotations

from pydantic import BaseModel, Field


class TranslateRequest(BaseModel):
    text: str = Field(
        min_length=1,
        max_length=500,
        description="Text to translate (typically a lemma or short phrase).",
    )
    source_language: str = Field(
        description="BCP-47 source language code (e.g. 'es', 'fr', 'ru').",
    )
    target_language: str = Field(
        default="en",
        description="BCP-47 target language code.  Default 'en' (English).",
    )
    object_id: str | None = Field(
        default=None,
        description=(
            "When provided, the translation is stored back to this canonical "
            "object's lesson_data so future lessons display it without a new API call."
        ),
    )


class TranslateResponse(BaseModel):
    text: str
    translation: str | None
    source_language: str
    target_language: str
    provider: str
    attribution: str
    cached: bool = Field(
        default=False,
        description="True when the result was served from lesson_data (no API call).",
    )
