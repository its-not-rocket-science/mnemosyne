"""Shared NLP + lesson-enrichment pipeline.

This module is the single source of truth for all NLP work:
  1. Redis cache check (return immediately on hit)
  2. plugin.analyze_text in a thread pool (CPU-bound; non-blocking)
  3. lesson_engine.enrich — normalise, augment, deduplicate candidates
  4. UUID resolution → SentenceResult / LearnableObject
  5. plugin.lesson_store population (DB-unavailable fallback)
  6. Redis cache write (non-fatal)

Both /parse and /ingest call run_pipeline().  Route handlers differ only in:
  • text normalisation (ingest normalises first; parse uses raw text)
  • DB persistence shape (ingest creates SourceDocument; parse does not)
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from dataclasses import dataclass, field

import backend.lesson_extraction.engine as lesson_engine
from backend.core.cache import get_json, set_json
from backend.parsing.canonical import canonical_object_id
from backend.parsing.contract import CONTRACT_CHECK, validate_result as _validate_result
from backend.schemas.parse import (
    CandidateObject,
    CandidateSentenceResult,
    LearnableObject,
    ParseResponse,
    SentenceResult,
)

logger = logging.getLogger(__name__)


def _restore_sentence_texts(text: str, plugin, candidate_results: list[CandidateSentenceResult]) -> list[CandidateSentenceResult]:
    """Restore sentence surface text from the source passage when possible.

    Some plugin/extractor stacks may accidentally emit term-only strings in
    ``CandidateSentenceResult.text``.  Reader rendering must always use the
    original passage sentence text, so we align by sentence index when plugin
    sentence splitting is available and lengths match.
    """
    try:
        source_sentences = plugin.split_sentences(text)
    except Exception:
        return candidate_results
    if len(source_sentences) != len(candidate_results):
        return candidate_results
    return [
        cr.model_copy(update={"text": source_sentences[i]})
        for i, cr in enumerate(candidate_results)
    ]

# Bump when pipeline output changes incompatibly so stale cached responses are
# automatically bypassed.  v3 adds lesson_engine enrichment to all callers.
_CACHE_VERSION = "3"


def pipeline_cache_key(text: str, language: str) -> str:
    """Stable Redis cache key for the NLP + enrichment output of (text, language)."""
    digest = hashlib.sha256(f"{language}:{text}".encode()).hexdigest()
    return f"parse:v{_CACHE_VERSION}:{digest}"


@dataclass
class PipelineResult:
    sentences: list[SentenceResult]
    # Empty when cache_hit=True.  Callers must not rely on these for new rows.
    candidate_results: list[CandidateSentenceResult] = field(default_factory=list)
    uuid_to_candidate: dict[str, tuple[str, CandidateObject]] = field(default_factory=dict)
    cache_hit: bool = False


async def run_pipeline(
    text: str,
    language: str,
    plugin,
    cache_key: str,
) -> PipelineResult:
    """Run the shared NLP + lesson-enrichment pipeline.

    Args:
        text:       Text to analyse.  Caller is responsible for normalisation.
        language:   BCP-47 language code.
        plugin:     Loaded plugin instance from the registry.
        cache_key:  Redis key; use pipeline_cache_key() to generate it.

    Returns:
        PipelineResult.  When cache_hit=True, only ``sentences`` is populated;
        ``candidate_results`` and ``uuid_to_candidate`` are empty.
    """
    # 1. Cache check.
    try:
        cached = await get_json(cache_key)
        if cached is not None:
            logger.debug("pipeline cache=HIT lang=%s chars=%d", language, len(text))
            return PipelineResult(
                sentences=ParseResponse.model_validate(cached).sentences,
                cache_hit=True,
            )
    except Exception:
        pass  # Redis unavailable — continue.

    # 2. NLP — CPU-bound; run in thread pool so the event loop is not blocked.
    t_nlp = time.perf_counter()
    candidate_results: list[CandidateSentenceResult] = await asyncio.to_thread(
        plugin.analyze_text, text
    )
    logger.debug(
        "pipeline nlp_ms=%.1f lang=%s sentences=%d",
        (time.perf_counter() - t_nlp) * 1000,
        language,
        len(candidate_results),
    )
    candidate_results = _restore_sentence_texts(text, plugin, candidate_results)

    # 2a. Contract validation (opt-in; set MNEMOSYNE_CONTRACT_CHECK=1).
    if CONTRACT_CHECK:
        for cr in candidate_results:
            report = _validate_result(cr, plugin, input_sentence=cr.text)
            if not report.ok:
                logger.warning(
                    "contract violations lang=%s sentence=%r\n%s",
                    language, cr.text, report,
                )

    # 3. Lesson enrichment — normalise, augment, and deduplicate candidates.
    candidate_results = lesson_engine.enrich(language, candidate_results, plugin.capabilities)

    # 4. UUID resolution.
    uuid_to_candidate: dict[str, tuple[str, CandidateObject]] = {}
    sentences: list[SentenceResult] = []

    for cand_result in candidate_results:
        resolved: list[LearnableObject] = []
        for cand in cand_result.candidates:
            obj_id = canonical_object_id(language, cand.type, cand.canonical_form)
            lo = LearnableObject(
                id=obj_id,
                language=language,
                type=cand.type,
                label=cand.label,
                lesson_data=cand.lesson_data,
                confidence=cand.confidence,
            )
            resolved.append(lo)
            uuid_to_candidate[obj_id] = (cand.canonical_form, cand)
        sentences.append(SentenceResult(text=cand_result.text, learnable_objects=resolved))

    # 5. Populate lesson_store for DB-unavailable fallback.
    for obj_id, (_, cand) in uuid_to_candidate.items():
        plugin.lesson_store[obj_id] = cand

    # 6. Cache write (non-fatal).
    try:
        await asyncio.ensure_future(
            set_json(cache_key, ParseResponse(sentences=sentences).model_dump(mode="json"))
        )
    except Exception:
        pass

    return PipelineResult(
        sentences=sentences,
        candidate_results=candidate_results,
        uuid_to_candidate=uuid_to_candidate,
    )
