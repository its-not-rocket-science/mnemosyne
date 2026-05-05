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
