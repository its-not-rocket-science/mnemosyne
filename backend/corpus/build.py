"""Full corpus build pipeline: acquire → normalise → chunk → parse → persist.

Each corpus entry is processed as a single source document whose ``id`` is
deterministic (UUID-v5 over language + title + author + source_url).  A
document already present in the database is skipped unless ``force=True``.

The build is resumable: interrupted builds can be re-run and will skip already-
ingested documents and continue from the first missing one.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.corpus.acquisition import fetch_text
from backend.corpus.cache import (
    DEFAULT_CACHE_DIR,
    is_cached,
    read_cache,
    write_cache,
)
from backend.corpus.chunking import DEFAULT_MAX_CHUNK_CHARS, Chunk, chunk_text
from backend.corpus.manifest import CorpusEntry
from backend.corpus.normalize import normalize_corpus_text
from backend.ingestion.validator import detect_dominant_script
from backend.models import SourceDocumentRow
from backend.parsing.pipeline import pipeline_cache_key, run_pipeline
from backend.parsing.plugin_loader import PluginRegistry
from backend.schemas.ingest import ContentType
from backend.services.parse_persistence import (
    create_source_document_row,
    create_source_progression_row,
    persist_chunk,
)
from backend.srs.knowledge import DEFAULT_USER_ID

logger = logging.getLogger(__name__)

# Namespace UUID for corpus source-document IDs.  Must remain constant;
# changing it invalidates all stored corpus resumability checks.
_CORPUS_NS = uuid.UUID("c0d4a3b2-f1e0-4d5c-9876-abcdef012345")


def corpus_source_document_id(entry: CorpusEntry) -> str:
    """Return a deterministic UUID-v5 for a corpus entry.

    The key combines language, title, author, and source_url so that the
    same manifest entry always maps to the same DB row, enabling idempotent
    re-runs.
    """
    key = "\x00".join([
        entry.language,
        entry.title,
        entry.author or "",
        entry.source_url,
    ])
    return str(uuid.uuid5(_CORPUS_NS, key))


@dataclass
class BuildResult:
    entry: CorpusEntry
    status: Literal["skipped", "acquired", "ingested", "failed", "dry_run"] = "failed"
    source_document_id: str = ""
    chunks_processed: int = 0
    sentences_total: int = 0
    objects_total: int = 0
    warnings: list[str] = field(default_factory=list)
    error: str | None = None


async def _is_already_ingested(db: AsyncSession, source_document_id: str) -> bool:
    result = await db.execute(
        select(SourceDocumentRow.id).where(SourceDocumentRow.id == source_document_id)
    )
    return result.scalar_one_or_none() is not None


async def acquire_entry(
    entry: CorpusEntry,
    *,
    force: bool = False,
    cache_dir: Path = DEFAULT_CACHE_DIR,
) -> str:
    """Download the entry's text and write it to the local cache.

    Returns the raw acquired text.  Skips download if cached and ``force``
    is False.

    Raises:
        httpx.HTTPStatusError / httpx.RequestError: on network failures.
        ValueError: if the response exceeds the size cap or body is empty.
    """
    if not force and is_cached(entry.language, entry.title, cache_dir):
        logger.info("corpus cache HIT lang=%s title=%r", entry.language, entry.title)
        return read_cache(entry.language, entry.title, cache_dir)

    raw_text = await asyncio.to_thread(fetch_text, entry.source_url)
    if not raw_text.strip():
        raise ValueError(f"Acquired text for '{entry.title}' is empty after extraction.")

    write_cache(entry.language, entry.title, raw_text, cache_dir)
    logger.info(
        "corpus cache WRITE lang=%s title=%r chars=%d",
        entry.language, entry.title, len(raw_text),
    )
    return raw_text


async def build_entry(
    entry: CorpusEntry,
    registry: PluginRegistry,
    db: AsyncSession,
    *,
    dry_run: bool = False,
    force: bool = False,
    cache_dir: Path = DEFAULT_CACHE_DIR,
    max_chunk_chars: int = DEFAULT_MAX_CHUNK_CHARS,
    user_id: str = DEFAULT_USER_ID,
) -> BuildResult:
    """Process one corpus entry end-to-end.

    Steps:
      1. Compute deterministic source_document_id.
      2. Skip if already in DB (unless force=True).
      3. Acquire text (from cache or network).
      4. Normalise.
      5. Chunk.
      6. For each chunk: run NLP pipeline + persist.
      7. Create SourceProgressionRow; commit.

    Args:
        entry:          Manifest entry to build.
        registry:       Loaded plugin registry.
        db:             Async DB session (caller manages lifecycle).
        dry_run:        If True, skip all DB writes; log what would happen.
        force:          Re-ingest even if the document is already in the DB.
        cache_dir:      Root directory for the local text cache.
        max_chunk_chars: Soft chunk size cap.
        user_id:        User to seed UserKnowledge rows for.

    Returns:
        BuildResult describing the outcome.
    """
    source_document_id = corpus_source_document_id(entry)
    result = BuildResult(entry=entry, source_document_id=source_document_id)

    # Plugin availability check.
    try:
        plugin = registry.get(entry.language)
    except KeyError as exc:
        result.status = "failed"
        result.error = str(exc)
        logger.warning("corpus build skip lang=%s — no plugin: %s", entry.language, exc)
        return result

    # Resumability: skip if already ingested.
    if not force and not dry_run:
        if await _is_already_ingested(db, source_document_id):
            result.status = "skipped"
            logger.info(
                "corpus skip already-ingested lang=%s title=%r id=%s",
                entry.language, entry.title, source_document_id,
            )
            return result

    # Acquire text.
    try:
        raw_text = await acquire_entry(entry, force=force, cache_dir=cache_dir)
    except Exception as exc:
        result.status = "failed"
        result.error = f"Acquisition failed: {exc}"
        logger.error("corpus acquire error lang=%s title=%r: %s", entry.language, entry.title, exc)
        return result

    if dry_run and not is_cached(entry.language, entry.title, cache_dir):
        result.status = "dry_run"
        result.warnings.append("Text not yet cached; run 'acquire' first.")
        return result

    # Normalise.
    try:
        normalised, norm_warnings = normalize_corpus_text(raw_text, entry.language)
    except ValueError as exc:
        result.status = "failed"
        result.error = f"Normalisation failed: {exc}"
        return result
    result.warnings.extend(norm_warnings)

    # Chunk.
    chunks: list[Chunk] = chunk_text(normalised, max_chars=max_chunk_chars, language=entry.language)
    if not chunks:
        result.status = "failed"
        result.error = "Chunking produced no output."
        return result

    if dry_run:
        result.status = "dry_run"
        result.chunks_processed = len(chunks)
        result.warnings.append(
            f"dry-run: would process {len(chunks)} chunk(s) "
            f"({len(normalised):,} chars) for '{entry.title}'"
        )
        return result

    script_hint = detect_dominant_script(normalised)

    # Create SourceDocumentRow once, before iterating chunks.
    await create_source_document_row(
        db,
        source_document_id=source_document_id,
        language=entry.language,
        content_type=ContentType.CORPUS.value,
        char_count=len(normalised),
        script_hint=script_hint,
        title=entry.title,
        author=entry.author,
        source_url=entry.source_url,
    )

    sentences_total = 0
    objects_total = 0

    for chunk in chunks:
        cache_key = pipeline_cache_key(chunk.text, entry.language)
        try:
            pipeline_result = await run_pipeline(
                text=chunk.text,
                language=entry.language,
                plugin=plugin,
                cache_key=cache_key,
            )
        except Exception as exc:
            logger.warning(
                "corpus pipeline error lang=%s title=%r chunk=%d: %s",
                entry.language, entry.title, chunk.chunk_index, exc,
            )
            continue

        try:
            await persist_chunk(
                db,
                source_document_id=source_document_id,
                language=entry.language,
                chunk_index=chunk.chunk_index,
                char_start=chunk.char_start,
                char_end=chunk.char_end,
                chunk_text=chunk.text,
                source_url=entry.source_url,
                candidate_results=pipeline_result.candidate_results,
                sentences=pipeline_result.sentences,
                uuid_to_candidate=pipeline_result.uuid_to_candidate,
                user_id=user_id,
            )
        except Exception as exc:
            logger.warning(
                "corpus persist error lang=%s title=%r chunk=%d: %s",
                entry.language, entry.title, chunk.chunk_index, exc,
            )
            continue

        sentences_total += len(pipeline_result.sentences)
        objects_total += len(pipeline_result.uuid_to_candidate)
        result.chunks_processed += 1

    # SourceProgressionRow — one per (user, document).
    try:
        await create_source_progression_row(
            db,
            user_id=user_id,
            source_document_id=source_document_id,
            sentences_total=sentences_total,
        )
        await db.commit()
    except Exception as exc:
        await db.rollback()
        result.status = "failed"
        result.error = f"Commit failed: {exc}"
        logger.error(
            "corpus commit error lang=%s title=%r: %s",
            entry.language, entry.title, exc,
        )
        return result

    result.status = "ingested"
    result.sentences_total = sentences_total
    result.objects_total = objects_total
    logger.info(
        "corpus ingested lang=%s title=%r chunks=%d sentences=%d objects=%d",
        entry.language, entry.title,
        result.chunks_processed, sentences_total, objects_total,
    )
    return result
