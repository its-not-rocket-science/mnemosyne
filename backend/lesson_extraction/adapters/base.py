from __future__ import annotations

from typing import Iterable

from backend.schemas.parse import CandidateObject
from ..types import PedagogyTag, with_pedagogy


class LessonExtractionAdapter:
    """Base adapter.

    Adapters may:
      1. enrich existing CandidateObjects by adding normalized pedagogy metadata;
      2. derive extra CandidateObjects from reliable signals already present.

    They should be conservative: never invent a morphology fact unless the
    plugin or captured summary already provided the signal.
    """

    language: str = "unknown"

    def enrich_existing(self, candidates: list[CandidateObject], sentence_text: str) -> list[CandidateObject]:
        return [
            self._default_enrich(candidate)
            for candidate in candidates
        ]

    def derive_additional(self, candidates: list[CandidateObject], sentence_text: str) -> list[CandidateObject]:
        return []

    def _default_enrich(self, candidate: CandidateObject) -> CandidateObject:
        if candidate.lesson_data.get("pedagogy"):
            return candidate

        if candidate.type == "vocabulary":
            tag = PedagogyTag(
                family="vocabulary",
                skill="lemma",
                level=self._level_from_candidate(candidate),
                why_it_matters="This word is a reusable building block for understanding real sentences.",
                prompt_hint="Notice the base form and part of speech.",
            )
        elif candidate.type in {"conjugation", "agreement", "case_agreement"}:
            tag = PedagogyTag(
                family="morphology",
                skill=str(candidate.type),
                level=self._level_from_candidate(candidate),
                why_it_matters="This form shows how grammar changes meaning inside a sentence.",
                prompt_hint="Compare the surface form with the base form.",
            )
        elif candidate.type in {"grammar", "nuance", "idiom", "phrase_family"}:
            tag = PedagogyTag(
                family="semantic_pattern",
                skill=str(candidate.type),
                level=self._level_from_candidate(candidate),
                why_it_matters="This pattern carries meaning beyond a simple word lookup.",
                prompt_hint="Ask what this construction contributes to the sentence.",
            )
        elif candidate.type == "script":
            tag = PedagogyTag(
                family="script",
                skill="character",
                level=self._level_from_candidate(candidate),
                why_it_matters="Script knowledge helps connect written forms to sound and meaning.",
            )
        elif candidate.type == "transliteration":
            tag = PedagogyTag(
                family="transliteration",
                skill="reading",
                level=self._level_from_candidate(candidate),
                why_it_matters="Romanization helps bridge native script and pronunciation.",
            )
        else:
            return candidate

        return candidate.model_copy(
            update={"lesson_data": with_pedagogy(candidate.lesson_data, tag)}
        )

    def _level_from_candidate(self, candidate: CandidateObject) -> int:
        """Map existing difficulty-ish metadata to a stable 1–5 level."""
        data = candidate.lesson_data or {}

        if "level" in data:
            try:
                return max(1, min(5, int(data["level"])))
            except Exception:
                pass

        cefr = str(data.get("cefr_level") or "").upper()
        if cefr:
            return {
                "A1": 1, "A2": 2,
                "B1": 3, "B2": 4,
                "C1": 5, "C2": 5,
            }.get(cefr, 3)

        confidence = candidate.confidence
        if confidence is not None and confidence < 0.55:
            return 4

        if candidate.type in {"script", "transliteration", "vocabulary"}:
            return 1
        if candidate.type in {"conjugation", "agreement", "case_agreement"}:
            return 2
        return 3


def candidate_key(candidate: CandidateObject) -> tuple[str, str]:
    return (str(candidate.type), candidate.canonical_form)
