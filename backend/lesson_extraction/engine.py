from __future__ import annotations

import logging
from collections.abc import Iterable

from backend.schemas.parse import CandidateObject, CandidateSentenceResult
from backend.nuance.cultural import extract_cultural_references
from .adapters.base import candidate_key
from .registry import get_adapter

logger = logging.getLogger(__name__)


def enrich(language: str, candidate_results: list[CandidateSentenceResult], capabilities=None) -> list[CandidateSentenceResult]:
    """Normalize and augment plugin candidates.

    This is intentionally pure and side-effect free:
      - no DB access
      - no network access
      - no mutation of input CandidateObjects

    It is safe to run in both /parse and /ingest before UUID resolution.
    """
    adapter = get_adapter(language)

    enriched_results: list[CandidateSentenceResult] = []

    for sent in candidate_results:
        try:
            existing = adapter.enrich_existing(list(sent.candidates), sent.text)
            derived = adapter.derive_additional(existing, sent.text)
            cultural = extract_cultural_references(sent.text, language)
            candidates = _dedupe_merge([*existing, *derived, *cultural])
            candidates = _drop_vocab_consumed_by_phrases(candidates)
        except Exception:
            logger.warning("lesson extraction failed lang=%s sentence=%r", language, sent.text[:120], exc_info=True)
            candidates = list(sent.candidates)

        enriched_results.append(
            CandidateSentenceResult(
                text=sent.text,
                candidates=candidates,
            )
        )

    return enriched_results


def _dedupe_merge(candidates: Iterable[CandidateObject]) -> list[CandidateObject]:
    """Deduplicate by stable canonical key.

    First candidate wins; later candidates can fill missing lesson_data fields
    but cannot overwrite labels/surface forms from the plugin hot path.
    """
    by_key: dict[tuple[str, str], CandidateObject] = {}

    for cand in candidates:
        key = candidate_key(cand)
        if key not in by_key:
            by_key[key] = cand
            continue

        prev = by_key[key]
        merged_data = dict(prev.lesson_data or {})
        for k, v in (cand.lesson_data or {}).items():
            if k not in merged_data or merged_data[k] in (None, "", [], {}):
                merged_data[k] = v

        by_key[key] = prev.model_copy(
            update={
                "lesson_data": merged_data,
                "confidence": prev.confidence if prev.confidence is not None else cand.confidence,
            }
        )

    return list(by_key.values())


_PHRASE_CONSUMING: frozenset[str] = frozenset({"phrase_family", "idiom"})


def _drop_vocab_consumed_by_phrases(candidates: list[CandidateObject]) -> list[CandidateObject]:
    """Remove vocabulary candidates whose surface token is part of a phrase_family or idiom.

    When the nuance extractor adds a phrase_family/idiom after the plugin already
    emitted vocabulary for individual tokens, this prevents double-tagging the same
    surface word as both a phrase component and a standalone vocabulary card.
    """
    consumed: set[str] = set()
    for obj in candidates:
        if obj.type in _PHRASE_CONSUMING and obj.surface_form:
            for word in obj.surface_form.lower().split():
                consumed.add(word)
    if not consumed:
        return candidates
    return [
        obj for obj in candidates
        if not (
            obj.type == "vocabulary"
            and obj.surface_form
            and obj.surface_form.lower() in consumed
        )
    ]
