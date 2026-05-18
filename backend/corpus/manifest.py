"""Pydantic v2 models for the corpus source manifest (corpora/manifest.yaml).

Validates structure, licenses, framework/level consistency, and duplicate URLs
before any acquisition or ingestion work begins.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from enum import Enum
from pathlib import Path
from typing import Annotated

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator

ALLOWED_LICENSES: frozenset[str] = frozenset({
    "public_domain",
    "cc0",
    "cc_by",
    "cc_by_sa",
    "cc_by_nc",
    "cc_by_nc_sa",
})

_CEFR_LEVELS: tuple[str, ...] = ("A1", "A2", "B1", "B2", "C1", "C2")
_JLPT_LEVELS: tuple[str, ...] = ("N5", "N4", "N3", "N2", "N1")
_HSK_LEVELS: tuple[str, ...] = ("HSK1", "HSK2", "HSK3", "HSK4", "HSK5", "HSK6")
# Granular TOPIK1-6 plus legacy TOPIK-I / TOPIK-II for backward compatibility.
_TOPIK_LEVELS: tuple[str, ...] = (
    "TOPIK-I", "TOPIK-II",          # legacy — kept for backward compat
    "TOPIK1", "TOPIK2", "TOPIK3",   # granular scale
    "TOPIK4", "TOPIK5", "TOPIK6",
)
# ClassicalReading and KoineReading use the same A1-C2 scale as CEFR.
_CLASSICAL_READING_LEVELS: tuple[str, ...] = _CEFR_LEVELS
_KOINE_READING_LEVELS:     tuple[str, ...] = _CEFR_LEVELS

_VALID_LEVELS: dict[str, tuple[str, ...]] = {
    "CEFR":            _CEFR_LEVELS,
    "JLPT":            _JLPT_LEVELS,
    "HSK":             _HSK_LEVELS,
    "TOPIK":           _TOPIK_LEVELS,
    "ClassicalReading": _CLASSICAL_READING_LEVELS,
    "KoineReading":    _KOINE_READING_LEVELS,
    "custom":          (),  # any string accepted
}


class Framework(str, Enum):
    CEFR             = "CEFR"
    JLPT             = "JLPT"
    HSK              = "HSK"
    TOPIK            = "TOPIK"
    CLASSICAL_READING = "ClassicalReading"
    KOINE_READING    = "KoineReading"
    CUSTOM           = "custom"


def _slugify(text: str) -> str:
    """Convert text to a URL-safe ASCII slug for use in manifest_id."""
    # Normalize unicode → ASCII approximations.
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", errors="ignore").decode("ascii")
    # Lower-case, replace non-alphanumerics with hyphens, collapse runs.
    text = re.sub(r"[^a-z0-9]+", "-", text.lower())
    return text.strip("-")[:60]


class CorpusEntry(BaseModel):
    language:       Annotated[str, Field(min_length=2, max_length=10)]
    framework:      Framework = Framework.CEFR
    level:          str
    cefr_equivalent: str | None = None
    title:          Annotated[str, Field(min_length=1, max_length=512)]
    author:         Annotated[str | None, Field(max_length=256)] = None
    year:           int | None = None
    source_url:     Annotated[str, Field(min_length=1)]
    source_name:    Annotated[str, Field(min_length=1, max_length=256)]
    license:        str
    genre:          str | None = None
    dialect:        str | None = None
    script:         str | None = None
    notes:          list[str] = Field(default_factory=list)
    manual_review:  bool = False
    """True when the URL or content needs human verification before ingestion."""

    # manifest_id may be provided explicitly; if absent it is computed.
    manifest_id: str | None = None
    """Stable identifier: {language}:{framework}:{level}:{slug}:{url_hash8}.
    Computed from other fields if not specified in the YAML."""

    @model_validator(mode="after")
    def _validate_level(self) -> "CorpusEntry":
        valid = _VALID_LEVELS.get(self.framework.value, ())
        if valid and self.level not in valid:
            raise ValueError(
                f"level '{self.level}' invalid for framework '{self.framework.value}'; "
                f"expected one of {valid}"
            )
        return self

    @model_validator(mode="after")
    def _validate_cefr_equivalent(self) -> "CorpusEntry":
        if self.cefr_equivalent is not None and self.cefr_equivalent not in _CEFR_LEVELS:
            raise ValueError(
                f"cefr_equivalent '{self.cefr_equivalent}' must be one of {_CEFR_LEVELS}"
            )
        return self

    @model_validator(mode="after")
    def _validate_license(self) -> "CorpusEntry":
        if self.license not in ALLOWED_LICENSES:
            raise ValueError(
                f"license '{self.license}' not in allowed set {sorted(ALLOWED_LICENSES)}"
            )
        return self

    @model_validator(mode="after")
    def _fill_manifest_id(self) -> "CorpusEntry":
        if self.manifest_id is None:
            slug = _slugify(self.title)
            url_hash = hashlib.sha256(self.source_url.encode()).hexdigest()[:8]
            object.__setattr__(
                self,
                "manifest_id",
                f"{self.language}:{self.framework.value}:{self.level}:{slug}:{url_hash}",
            )
        return self

    @property
    def effective_cefr(self) -> str | None:
        """The CEFR level for this entry: explicit cefr_equivalent or level if CEFR."""
        if self.cefr_equivalent:
            return self.cefr_equivalent
        if self.framework == Framework.CEFR:
            return self.level if self.level in _CEFR_LEVELS else None
        return None


class CorpusManifest(BaseModel):
    entries: list[CorpusEntry] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_duplicate_urls(self) -> "CorpusManifest":
        seen: dict[str, str] = {}
        for entry in self.entries:
            key = entry.source_url
            if key in seen:
                raise ValueError(
                    f"Duplicate source_url '{key}' in entries "
                    f"'{seen[key]}' and '{entry.title}'"
                )
            seen[key] = entry.title
        return self

    def for_language(self, language: str) -> list[CorpusEntry]:
        return [e for e in self.entries if e.language.lower() == language.lower()]

    def languages(self) -> list[str]:
        return sorted({e.language for e in self.entries})

    def cefr_coverage(self, language: str) -> set[str]:
        """Return the set of CEFR levels covered for a given language."""
        result: set[str] = set()
        for e in self.for_language(language):
            c = e.effective_cefr
            if c:
                result.add(c)
        return result

    def missing_cefr_levels(self, language: str) -> list[str]:
        """Return CEFR levels not yet represented for a given language."""
        covered = self.cefr_coverage(language)
        return [lvl for lvl in _CEFR_LEVELS if lvl not in covered]


def load_manifest(path: Path) -> CorpusManifest:
    """Load and validate a corpus manifest YAML file."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if raw is None:
        return CorpusManifest(entries=[])
    return CorpusManifest.model_validate(raw)
