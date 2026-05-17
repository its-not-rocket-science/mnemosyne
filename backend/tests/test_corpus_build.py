"""Tests for the corpus build pipeline (mocked plugin + in-memory DB)."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.corpus.build import BuildResult, build_entry, corpus_source_document_id
from backend.corpus.manifest import CorpusEntry, Framework
from backend.models import Base
from backend.parsing.plugin_loader import PluginRegistry
from backend.schemas.parse import CandidateSentenceResult, LearnableObject, SentenceResult


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_entry() -> CorpusEntry:
    return CorpusEntry(
        language="en",
        framework=Framework.CEFR,
        level="B2",
        cefr_equivalent="B2",
        title="Test Story",
        author="Test Author",
        year=1900,
        source_url="https://example.com/test.txt",
        source_name="Test Source",
        license="public_domain",
    )


@pytest.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


def _make_registry(language: str = "en") -> PluginRegistry:
    """Build a minimal PluginRegistry with a stub plugin."""
    registry = PluginRegistry()
    plugin = MagicMock()
    plugin.language_code = language
    plugin.lesson_store = {}

    from backend.schemas.language import LanguageCapabilities
    plugin.capabilities = LanguageCapabilities(
        code=language,
        display_name=language.upper(),
        direction="ltr",
        script_family="latin",
        tokenization_mode="whitespace",
        morphology_depth="none",
        lesson_modes_supported=["dictionary"],
    )
    plugin.analyze_text.return_value = [
        CandidateSentenceResult(text="Hello world.", candidates=[])
    ]
    plugin.split_sentences.return_value = ["Hello world."]
    registry.register(plugin)
    return registry


# ── corpus_source_document_id ─────────────────────────────────────────────────

def test_deterministic_id(sample_entry: CorpusEntry):
    id1 = corpus_source_document_id(sample_entry)
    id2 = corpus_source_document_id(sample_entry)
    assert id1 == id2


def test_different_entries_different_ids(sample_entry: CorpusEntry):
    other = sample_entry.model_copy(update={"title": "Different Book"})
    assert corpus_source_document_id(sample_entry) != corpus_source_document_id(other)


# ── build_entry — dry run ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_build_dry_run_no_db_write(
    sample_entry: CorpusEntry,
    db_session: AsyncSession,
    tmp_path: Path,
):
    registry = _make_registry("en")
    # Pre-cache a small text so dry-run can proceed.
    cache_dir = tmp_path / "cache"
    from backend.corpus.cache import write_cache
    write_cache("en", sample_entry.title, "Hello world.\n\nSecond paragraph.", cache_dir)

    result = await build_entry(
        sample_entry,
        registry,
        db_session,
        dry_run=True,
        cache_dir=cache_dir,
    )
    assert result.status == "dry_run"

    # No SourceDocumentRow should have been written.
    from sqlalchemy import select
    from backend.models import SourceDocumentRow
    rows = (await db_session.execute(select(SourceDocumentRow))).scalars().all()
    assert rows == []


# ── build_entry — no plugin ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_build_unknown_language_returns_failed(
    sample_entry: CorpusEntry,
    db_session: AsyncSession,
    tmp_path: Path,
):
    empty_registry = PluginRegistry()
    result = await build_entry(
        sample_entry,
        empty_registry,
        db_session,
        cache_dir=tmp_path,
    )
    assert result.status == "failed"
    assert result.error is not None


# ── build_entry — acquisition failure ────────────────────────────────────────

@pytest.mark.asyncio
async def test_build_acquisition_failure_returns_failed(
    sample_entry: CorpusEntry,
    db_session: AsyncSession,
    tmp_path: Path,
):
    registry = _make_registry("en")
    with patch("backend.corpus.build.fetch_text", side_effect=OSError("Network error")):
        result = await build_entry(
            sample_entry,
            registry,
            db_session,
            cache_dir=tmp_path / "empty_cache",
        )
    assert result.status == "failed"
    assert "Acquisition failed" in (result.error or "")


# ── build_entry — successful ingest ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_build_entry_full_pipeline(
    sample_entry: CorpusEntry,
    db_session: AsyncSession,
    tmp_path: Path,
):
    registry = _make_registry("en")
    cache_dir = tmp_path / "cache"

    from backend.corpus.cache import write_cache
    write_cache(
        "en",
        sample_entry.title,
        "Hello world. This is a test.\n\nAnother paragraph here.",
        cache_dir,
    )

    # Patch run_pipeline to return a minimal result without loading spaCy.
    from backend.parsing.pipeline import PipelineResult
    mock_pipeline = AsyncMock(return_value=PipelineResult(
        sentences=[SentenceResult(text="Hello world.", learnable_objects=[])],
        candidate_results=[CandidateSentenceResult(text="Hello world.", candidates=[])],
        uuid_to_candidate={},
    ))

    with patch("backend.corpus.build.run_pipeline", mock_pipeline):
        result = await build_entry(
            sample_entry,
            registry,
            db_session,
            cache_dir=cache_dir,
        )

    assert result.status == "ingested"
    assert result.chunks_processed >= 1

    from sqlalchemy import select
    from backend.models import SourceDocumentRow
    rows = (await db_session.execute(select(SourceDocumentRow))).scalars().all()
    assert len(rows) == 1
    assert rows[0].language == "en"
    assert rows[0].title == "Test Story"
    assert rows[0].content_type == "corpus"


# ── build_entry — resumability ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_build_entry_skips_already_ingested(
    sample_entry: CorpusEntry,
    db_session: AsyncSession,
    tmp_path: Path,
):
    registry = _make_registry("en")
    cache_dir = tmp_path / "cache"

    from backend.corpus.cache import write_cache
    write_cache("en", sample_entry.title, "Hello world.", cache_dir)

    from backend.parsing.pipeline import PipelineResult
    mock_pipeline = AsyncMock(return_value=PipelineResult(
        sentences=[SentenceResult(text="Hello world.", learnable_objects=[])],
        candidate_results=[CandidateSentenceResult(text="Hello world.", candidates=[])],
        uuid_to_candidate={},
    ))

    with patch("backend.corpus.build.run_pipeline", mock_pipeline):
        # First build: should ingest.
        r1 = await build_entry(sample_entry, registry, db_session, cache_dir=cache_dir)
        assert r1.status == "ingested"

        # Second build (new session not needed — same session): should skip.
        r2 = await build_entry(sample_entry, registry, db_session, cache_dir=cache_dir)
        assert r2.status == "skipped"
