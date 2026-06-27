"""Pydantic v2 schemas for POST /fetch-url and POST /detect-language."""
from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class FetchUrlRequest(BaseModel):
    source_url: str = Field(
        min_length=8,
        max_length=2048,
        description="The URL to fetch.  Must use the http or https scheme.",
    )

    @field_validator("source_url")
    @classmethod
    def must_be_http_or_https(cls, v: str) -> str:
        stripped = v.strip()
        lower = stripped.lower()
        if not (lower.startswith("http://") or lower.startswith("https://")):
            raise ValueError(
                "Only http:// and https:// URLs are supported."
            )
        return stripped


class FetchUrlResponse(BaseModel):
    """Result of fetching and extracting text from a URL."""
    source_url: str = Field(description="Final URL after redirects.")
    title: str | None = Field(default=None, description="Page title, if detected.")
    text: str = Field(description="Extracted plain text.")
    char_count: int = Field(description="Length of the extracted text in characters.")
    detected_language: str | None = Field(
        default=None,
        description=(
            "BCP-47 language code detected from the extracted text, or null "
            "when confidence is too low."
        ),
    )


class DetectLanguageRequest(BaseModel):
    text: str = Field(
        min_length=1,
        description="Text sample to classify.  Longer samples give better results.",
    )


class DetectLanguageResponse(BaseModel):
    """Language detection result."""
    language: str | None = Field(
        description=(
            "BCP-47 language code, or null when detection confidence is too low "
            "or the text is too short."
        ),
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Detection confidence in [0, 1].  Values below 0.5 are weak.",
    )
    supported: bool = Field(
        description=(
            "True when *language* has a registered plugin in this deployment."
        ),
    )
