"""Full corpus build pipeline: acquire → normalise → chunk → parse → persist.

Each corpus entry is processed as a single source document whose ``id`` is
deterministic (UUID-v5 over language + title + author + source_url).

Idempotency
-----------
Three levels of idempotency are enforced:

1. DB check: if SourceDocumentRow already exists, skip unless ``force=True``.
2. Lockfile check: if the entry's normalized_content_hash in the lockfile
   matches the freshly-computed hash, and the DB row exists, skip.
3. Metadata-only: if only the manifest entry metadata changed (manifest_entry_hash
   differs but content hashes are the same), update the lockfile without reparsing.

The build is resumable: interrupted builds can be re-run and will skip already-
ingested documents and continue from the first missing one.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.corpus.acquisition import fetch_text
from backend.corpus.cache import (
    DEFAULT_CACHE_DIR,
    is_cached,
    read_cache,
    write_cache,
)
from backend.corpus.chunking import DEFAULT_MAX_CHUNK_CHARS, Chunk, chunk_text
from backend.corpus.lockfile import (
    DEFAULT_LOCKFILE,
    LockEntry,
    load_lockfile,
    save_lockfile,
    update_lock_entry,
)
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

PIPELINE_VERSION = "1.0"


# ── Hashing helpers ────────────────────────────────────────────────────────────

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


def _source_identity(entry: CorpusEntry) -> str:
    """sha256 of the stable source identity fields (first 64 hex chars)."""
    key = "\x00".join([
        entry.language,
        entry.framework.value,
        entry.level,
        entry.source_url.strip().lower(),
        entry.title.strip(),
        entry.author or "",
    ])
    return hashlib.sha256(key.encode()).hexdigest()[:64]


def _manifest_entry_hash(entry: CorpusEntry) -> str:
    """sha256 of the serialised manifest entry (detects any metadata change)."""
    data = entry.model_dump(mode="json")
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()[:64]


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:64]


# ── Build result ───────────────────────────────────────────────────────────────

@dataclass
class BuildResult:
    entry: CorpusEntry
    status: Literal["skipped", "acquired", "ingested", "metadata_only", "failed", "dry_run"] = "failed"
    source_document_id: str = ""
    chunks_processed: int = 0
    sentences_total: int = 0
    objects_total: int = 0
    warnings: list[str] = field(default_factory=list)
    error: str | None = None


# ── DB helpers ─────────────────────────────────────────────────────────────────

async def _is_already_ingested(db: AsyncSession, source_document_id: str) -> bool:
    result = await db.execute(
        select(SourceDocumentRow.id).where(SourceDocumentRow.id == source_document_id)
    )
    return result.scalar_one_or_none() is not None


# ── Acquire ────────────────────────────────────────────────────────────────────

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


# ── Build ──────────────────────────────────────────────────────────────────────

async def build_entry(
    entry: CorpusEntry,
    registry: PluginRegistry,
    db: AsyncSession,
    *,
    dry_run: bool = False,
    force: bool = False,
    only_new: bool = False,
    skip_existing: bool = False,
    cache_dir: Path = DEFAULT_CACHE_DIR,
    max_chunk_chars: int = DEFAULT_MAX_CHUNK_CHARS,
    user_id: str = DEFAULT_USER_ID,
    lockfile_path: Path = DEFAULT_LOCKFILE,
) -> BuildResult:
    """Process one corpus entry end-to-end.

    Steps:
      1. Compute deterministic source_document_id + identity hashes.
      2. Check lockfile + DB for skip conditions.
      3. Acquire text (from cache or network).
      4. Compute content hashes; detect metadata-only changes.
      5. Normalise.
      6. Chunk.
      7. For each chunk: run NLP pipeline + persist.
      8. Create SourceProgressionRow; commit.
      9. Update lockfile.

    Args:
        entry:           Manifest entry to build.
        registry:        Loaded plugin registry.
        db:              Async DB session (caller manages lifecycle).
        dry_run:         If True, skip all DB writes; log what would happen.
        force:           Re-ingest even if the document is already in the DB.
        only_new:        Skip if ANY prior ingestion record exists in lockfile.
        skip_existing:   Skip if DB row exists (alias for the default behaviour).
        cache_dir:       Root directory for the local text cache.
        max_chunk_chars: Soft chunk size cap.
        user_id:         User to seed UserKnowledge rows for.
        lockfile_path:   Path to the manifest lockfile.

    Returns:
        BuildResult describing the outcome.
    """
    source_document_id = corpus_source_document_id(entry)
    result = BuildResult(entry=entry, source_document_id=source_document_id)
    mid = entry.manifest_id or ""
    me_hash = _manifest_entry_hash(entry)
    si = _source_identity(entry)

    # Load lockfile.
    lock_data = load_lockfile(lockfile_path)
    lock_entry: LockEntry = lock_data.get(mid, {})  # type: ignore[assignment]

    # Plugin availability check.
    try:
        plugin = registry.get(entry.language)
    except KeyError as exc:
        result.status = "failed"
        result.error = str(exc)
        logger.warning("corpus build skip lang=%s — no plugin: %s", entry.language, exc)
        return result

    # manual_review entries must be resolved by a human before ingestion.
    if entry.manual_review:
        result.status = "skipped"
        result.warnings.append("manual_review=True; fix URL before ingesting")
        logger.info(
            "corpus skip manual_review lang=%s title=%r", entry.language, entry.title,
        )
        return result

    # --only-new: skip if lockfile has any prior record.
    if only_new and lock_entry.get("ingestion_status") in ("ok", "skipped", "metadata_only"):
        result.status = "skipped"
        logger.info("corpus --only-new skip lang=%s title=%r", entry.language, entry.title)
        return result

    # DB resumability: skip if already ingested (unless force).
    if not force and not dry_run:
        if await _is_already_ingested(db, source_document_id):
            # Check if this is a metadata-only change.
            if lock_entry.get("manifest_entry_hash") != me_hash:
                update_lock_entry(
                    lock_data, mid,
                    manifest_entry_hash=me_hash,
                    ingestion_status="metadata_only",
                )
                if not dry_run:
                    save_lockfile(lock_data, lockfile_path)
                result.status = "metadata_only"
                logger.info(
                    "corpus metadata-only update lang=%s title=%r",
                    entry.language, entry.title,
                )
                return result

            result.status = "skipped"
            logger.info(
                "corpus skip already-ingested lang=%s title=%r id=%s",
                entry.language, entry.title, source_document_id,
            )
            return result

    # In dry_run mode, skip network I/O if text is not already cached.
    if dry_run and not is_cached(entry.language, entry.title, cache_dir):
        result.status = "dry_run"
        result.warnings.append("Text not yet cached; run 'acquire' first.")
        return result

    # Acquire text.
    try:
        raw_text = await acquire_entry(entry, force=force, cache_dir=cache_dir)
    except Exception as exc:
        result.status = "failed"
        result.error = f"Acquisition failed: {exc}"
        logger.error("corpus acquire error lang=%s title=%r: %s", entry.language, entry.title, exc)
        return result

    raw_hash = _content_hash(raw_text)

    # Normalise.
    try:
        normalised, norm_warnings = normalize_corpus_text(raw_text, entry.language)
    except ValueError as exc:
        result.status = "failed"
        result.error = f"Normalisation failed: {exc}"
        return result
    result.warnings.extend(norm_warnings)
    norm_hash = _content_hash(normalised)

    # Check if content is unchanged (normalized hash matches lockfile).
    if not force and lock_entry.get("normalized_content_hash") == norm_hash:
        # Content identical; only metadata may have changed.
        if lock_entry.get("manifest_entry_hash") != me_hash:
            update_lock_entry(
                lock_data, mid,
                manifest_entry_hash=me_hash,
                ingestion_status="metadata_only",
            )
            if not dry_run:
                save_lockfile(lock_data, lockfile_path)
        result.status = "metadata_only"
        logger.info(
            "corpus content-unchanged skip lang=%s title=%r",
            entry.language, entry.title,
        )
        return result

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

    # --force: delete existing document (and cascade) before re-inserting.
    if force:
        await db.execute(
            delete(SourceDocumentRow).where(SourceDocumentRow.id == source_document_id)
        )
        await db.flush()

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

        # Savepoint isolates each chunk: a failed flush won't invalidate the
        # outer transaction or poison subsequent chunks.
        try:
            async with db.begin_nested():
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

    # Update lockfile.
    update_lock_entry(
        lock_data, mid,
        manifest_entry_hash=me_hash,
        raw_content_hash=raw_hash,
        normalized_content_hash=norm_hash,
        ingestion_status="ok",
    )
    save_lockfile(lock_data, lockfile_path)

    return result
