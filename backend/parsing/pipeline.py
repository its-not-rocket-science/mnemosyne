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
    sentence splitting is available.

    When source and candidate counts match, we do a direct index-for-index
    replacement.  When they differ (e.g. the model over-splits a passage into
    many single-token "sentences"), we merge the over-split candidate results
    back onto the source sentences so the reader never shows word-per-card
    gibberish.
    """
    try:
        source_sentences = plugin.split_sentences(text)
    except Exception:
        return candidate_results

    n_src = len(source_sentences)
    n_cand = len(candidate_results)

    if n_src == 0 or n_cand == 0:
        return candidate_results

    # Fast path: counts match — straightforward index replacement.
    if n_src == n_cand:
        return [
            cr.model_copy(update={"text": source_sentences[i]})
            for i, cr in enumerate(candidate_results)
        ]

    # Slow path: plugin over-split (n_cand > n_src).
    # Distribute candidate results across source sentences by greedy prefix
    # matching: assign each candidate result to the source sentence whose
    # prefix best overlaps with the candidate text.  When in doubt, pack
    # into the fewest source sentences to avoid losing candidates.
    if n_cand > n_src:
        # Build a mapping: source_idx → merged CandidateSentenceResult.
        # Score each candidate against each source sentence by word overlap.
        buckets: list[list[CandidateSentenceResult]] = [[] for _ in range(n_src)]
        src_word_sets = [
            set(s.lower().split()) for s in source_sentences
        ]
        for cr in candidate_results:
            cand_words = set((cr.text or "").lower().split())
            best = 0
            best_score = -1
            for si, src_words in enumerate(src_word_sets):
                score = len(cand_words & src_words)
                if score > best_score:
                    best_score = score
                    best = si
            buckets[best].append(cr)
        merged: list[CandidateSentenceResult] = []
        for si, (src_text, bucket) in enumerate(zip(source_sentences, buckets)):
            if not bucket:
                # No candidates mapped here — emit an empty sentence.
                merged.append(CandidateSentenceResult(text=src_text, candidates=[]))
            else:
                all_candidates = [c for cr in bucket for c in cr.candidates]
                merged.append(bucket[0].model_copy(update={"text": src_text, "candidates": all_candidates}))
        return merged

    # Plugin under-split (n_cand < n_src): can't safely expand; just restore
    # what we can and leave the tail as-is.
    restored = [
        cr.model_copy(update={"text": source_sentences[i]})
        for i, cr in enumerate(candidate_results)
    ]
    return restored

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
