"""User-specific enrichment data threaded into lesson generation.

``LessonEnrichmentContext`` is assembled by the GET /lesson route from
UserKnowledgeRow, TermProgressRow, and ObjectRelationRow queries.  It is
passed to ``build_lesson()`` as an optional argument so that:

  - The lesson generator stays pure/deterministic for a given input.
  - Existing callers that pass no enrichment continue to work unchanged.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from backend.schemas.lesson import EncounteredVocabularySummary


@dataclass
class LessonEnrichmentContext:
    """User-specific progress snapshot for a single lesson request.

    mastery_score
        Latest FSRS mastery score [0, 1] for this canonical object.
        ``None`` when the user has never reviewed it.

    exposure_count
        How many times this surface form has been encountered during parsing
        (sourced from ``TermProgressRow.exposure_count``).

    related_vocabulary
        Vocabulary items linked to this object via ``conjugation_of`` /
        ``agreement_of`` / ``nuance_of`` relations.  Populates
        ``LessonResponse.encountered_vocabulary``.
    """
    mastery_score: float | None = None
    exposure_count: int = 0
    related_vocabulary: list[EncounteredVocabularySummary] = field(default_factory=list)
