"""NuanceExtractor protocol — shared contract for all language-specific extractors."""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from backend.schemas.parse import CandidateObject


@runtime_checkable
class NuanceExtractor(Protocol):
    """Called once per sentence after plugin analysis.

    Receives the raw sentence text, plugin tokens, and the initial candidate
    list. Returns additional ``type="nuance"`` CandidateObjects. Must not
    mutate the input candidates list.

    Canonical-form convention: ``nuance:{lang}:{nuance_type}:{key}``
    Required lesson_data keys: nuance_type, explanation, register,
    learner_level, source.
    """

    language: str

    def extract_nuance(
        self,
        sentence: str,
        tokens: list[Any],
        candidates: list[CandidateObject],
        language: str,
    ) -> list[CandidateObject]: ...


class NuanceExtractorMixin:
    """Shared helpers for all language nuance extractors.

    Provides _cultural_references() and _merge_candidates() so each
    extractor can wire in the generated catalogue without duplicating code.
    Subclasses must set self.language.
    """

    language: str

    def _cultural_references(self, sentence_text: str) -> list[CandidateObject]:
        from backend.nuance.cultural import extract_cultural_references
        try:
            return extract_cultural_references(sentence_text, self.language)
        except Exception:
            return []

    def _merge_candidates(
        self,
        primary: list[CandidateObject],
        secondary: list[CandidateObject],
    ) -> list[CandidateObject]:
        """Merge two candidate lists, deduplicating by surface form.

        primary (System A / old phrase_families) takes precedence. Secondary
        results that don't overlap any primary surface form are appended.
        """
        if not secondary:
            return primary
        if not primary:
            return secondary

        primary_surfaces: set[str] = {(c.surface_form or "").lower() for c in primary}
        merged = list(primary)
        for c in secondary:
            sf = (c.surface_form or "").lower()
            if sf not in primary_surfaces:
                merged.append(c)
                primary_surfaces.add(sf)
        return merged
