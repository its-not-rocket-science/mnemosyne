"""Lesson-build context — language-level metadata passed into every builder.

``LessonContext`` decouples builders from the full ``LanguageCapabilities``
schema so individual builders stay testable without a live plugin, and so
future providers (gloss, pronunciation) can also receive language information
without importing the plugin stack.

Design notes
────────────
``language_name`` is ``None`` for unknown languages so builders can write
grammatically natural fallbacks:
  - None  →  '"por supuesto" is an idiomatic expression.'
  - "Spanish"  →  '"por supuesto" is a Spanish idiom meaning "of course".'

``language_code`` is ``None`` for unknown languages.  Provider
implementations receive it as-is and should treat ``None`` as "no-op".

``is_rtl`` and ``is_cjk`` are derived properties used by builders that need
to adjust field labels or explanation text for right-to-left or CJK scripts.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from backend.schemas.language import LanguageCapabilities


@dataclass(frozen=True, slots=True)
class LessonContext:
    """Language-level context threaded through the lesson build pipeline.

    All fields are optional so callers that do not have full plugin metadata
    can still construct a context with whatever they know.
    """

    language_code: str | None = None
    """BCP-47 language code, e.g. ``"es"`` or ``"de"``.  None = unknown."""

    language_name: str | None = None
    """Human-readable language name, e.g. ``"Spanish"``.  None = unknown."""

    script_family: str = "latin"
    """Broad script category — ``"latin"`` | ``"arabic"`` | ``"cjk"`` | …"""

    direction: Literal["ltr", "rtl"] = "ltr"
    """Text direction for explanation copy and TTS hint."""

    # ── Derived properties ────────────────────────────────────────────────────

    @property
    def is_rtl(self) -> bool:
        """True when text runs right-to-left (Arabic, Hebrew, …)."""
        return self.direction == "rtl"

    @property
    def is_cjk(self) -> bool:
        """True for CJK scripts where character lessons are primary."""
        return self.script_family == "cjk"

    # ── Factory helpers ───────────────────────────────────────────────────────

    @classmethod
    def from_capabilities(cls, caps: "LanguageCapabilities") -> "LessonContext":
        """Build a context from a plugin's ``LanguageCapabilities`` object."""
        return cls(
            language_code=caps.code,
            language_name=caps.display_name,
            script_family=caps.script_family,
            direction=caps.direction,
        )

    @classmethod
    def unknown(cls) -> "LessonContext":
        """Return a context for when no language information is available.

        Builders gracefully omit language-specific prose (e.g. "Spanish idiom"
        → "idiomatic expression") rather than asserting unknown language names.
        """
        return cls()
