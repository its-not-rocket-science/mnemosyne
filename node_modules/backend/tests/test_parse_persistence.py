"""Tests for TermProgressRow tracking in persist_chunk / persist_ingest."""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.models import Base, TermProgressRow
from backend.parsing.canonical import canonical_object_id
from backend.schemas.parse import (
    CandidateObject,
    CandidateSentenceResult,
    SentenceResult,
)
from backend.services.parse_persistence import persist_ingest

# ── fixtures ─────────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def db_engine(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/tp_test.db")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db(db_engine):
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session


# ── helpers ───────────────────────────────────────────────────────────────────


def _vocab_cand(
    surface: str,
    lemma: str,
    canonical: str | None = None,
    type_: str = "vocabulary",
) -> CandidateObject:
    cf = canonical or lemma
    return CandidateObject(
        canonical_form=cf,
        type=type_,
        label=surface,
        surface_form=surface,
        lesson_data={"lemma": lemma},
    )


def _build_ingest_args(
    cands: list[CandidateObject],
    language: str,
    source_document_id: str | None = None,
    user_id: str = "test-user",
) -> dict:
    sdid = source_document_id or str(uuid.uuid4())
    uuid_to_candidate = {
        canonical_object_id(language, c.type, c.canonical_form): (c.canonical_form, c)
        for c in cands
    }
    candidate_results = [CandidateSentenceResult(text="x", candidates=cands)]
    sentences: list[SentenceResult] = []
    return dict(
        language=language,
        content_type="text",
        normalized_text="x",
        script_hint=None,
        source_document_id=sdid,
        candidate_results=candidate_results,
        sentences=sentences,
        uuid_to_candidate=uuid_to_candidate,
        user_id=user_id,
    )


# ── tests ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_first_exposure_creates_term_progress_row(db):
    cand = _vocab_cand("casa", "casa")
    await persist_ingest(db, **_build_ingest_args([cand], "es"))

    row = await db.get(TermProgressRow, ("test-user", "es", "casa"))
    assert row is not None
    assert row.lemma == "casa"
    assert row.exposure_count == 1
    assert row.first_seen is not None
    assert row.last_seen is not None
    assert row.source_lesson_ids != []


@pytest.mark.asyncio
async def test_repeated_exposure_increments_count(db):
    cand = _vocab_cand("casa", "casa")
    args = _build_ingest_args([cand], "es")
    # Two separate parse calls — exposure_count must reach 2.
    await persist_ingest(db, **{**args, "source_document_id": str(uuid.uuid4())})
    await persist_ingest(db, **{**args, "source_document_id": str(uuid.uuid4())})

    row = await db.get(TermProgressRow, ("test-user", "es", "casa"), populate_existing=True)
    assert row is not None
    assert row.exposure_count == 2


@pytest.mark.asyncio
async def test_different_users_isolated(db):
    cand = _vocab_cand("libro", "libro")
    await persist_ingest(db, **_build_ingest_args([cand], "es", user_id="alice"))
    await persist_ingest(db, **_build_ingest_args([cand], "es", user_id="bob"))

    alice_row = await db.get(TermProgressRow, ("alice", "es", "libro"))
    bob_row   = await db.get(TermProgressRow, ("bob",   "es", "libro"))
    assert alice_row is not None
    assert bob_row is not None
    assert alice_row.exposure_count == 1
    assert bob_row.exposure_count == 1


@pytest.mark.asyncio
async def test_different_languages_isolated(db):
    cand_es = _vocab_cand("libro", "libro")
    cand_pt = _vocab_cand("livro", "livro")
    await persist_ingest(db, **_build_ingest_args([cand_es], "es"))
    await persist_ingest(db, **_build_ingest_args([cand_pt], "pt"))

    es_row = await db.get(TermProgressRow, ("test-user", "es", "libro"))
    pt_row = await db.get(TermProgressRow, ("test-user", "pt", "livro"))
    # No cross-language contamination
    wrong = await db.get(TermProgressRow, ("test-user", "pt", "libro"))
    assert es_row is not None
    assert pt_row is not None
    assert wrong is None


@pytest.mark.asyncio
async def test_source_lesson_ids_no_duplicates(db):
    cand = _vocab_cand("hablar", "hablar")
    obj_id = canonical_object_id("es", cand.type, cand.canonical_form)
    args = _build_ingest_args([cand], "es")

    # Three parses with the same candidate → obj_id must appear only once.
    for _ in range(3):
        await persist_ingest(db, **{**args, "source_document_id": str(uuid.uuid4())})

    row = await db.get(TermProgressRow, ("test-user", "es", "hablar"), populate_existing=True)
    assert row is not None
    assert row.exposure_count == 3
    assert row.source_lesson_ids.count(obj_id) == 1


@pytest.mark.asyncio
async def test_non_vocab_types_not_tracked(db):
    """Idiom and grammar candidates must not create TermProgressRow entries."""
    idiom = CandidateObject(
        canonical_form="echar de menos",
        type="idiom",
        label="echar de menos",
        surface_form="echar de menos",
        lesson_data={},
    )
    grammar = CandidateObject(
        canonical_form="subjunctive doubt",
        type="grammar",
        label="subjunctive doubt",
        surface_form=None,
        lesson_data={},
    )
    args = _build_ingest_args([idiom, grammar], "es")
    await persist_ingest(db, **args)

    from sqlalchemy import select
    result = await db.execute(
        select(TermProgressRow).where(TermProgressRow.user_id == "test-user")
    )
    rows = list(result.scalars())
    assert rows == []


@pytest.mark.asyncio
async def test_conjugation_type_tracked(db):
    """conjugation objects are vocab-like and must be tracked."""
    cand = _vocab_cand("hablo", "hablar", canonical="hablar:present:indicative:1:Sing", type_="conjugation")
    await persist_ingest(db, **_build_ingest_args([cand], "es"))

    row = await db.get(TermProgressRow, ("test-user", "es", "hablo"))
    assert row is not None
    assert row.lemma == "hablar"
    assert row.exposure_count == 1


@pytest.mark.asyncio
async def test_inflection_type_tracked(db):
    """inflection objects are vocab-like and must be tracked."""
    cand = _vocab_cand("lupi", "lupus", canonical="lupus:genitive:Sing", type_="inflection")
    await persist_ingest(db, **_build_ingest_args([cand], "la"))

    row = await db.get(TermProgressRow, ("test-user", "la", "lupi"))
    assert row is not None
    assert row.lemma == "lupus"


@pytest.mark.asyncio
async def test_duplicate_in_one_sentence_counts_twice(db):
    """Same term twice in one CandidateSentenceResult → exposure_count == 2."""
    cand = _vocab_cand("casa", "casa")
    sdid = str(uuid.uuid4())
    uuid_to_candidate = {
        canonical_object_id("es", cand.type, cand.canonical_form): (cand.canonical_form, cand)
    }
    candidate_results = [CandidateSentenceResult(text="casa y casa", candidates=[cand, cand])]
    await persist_ingest(
        db,
        language="es",
        content_type="text",
        normalized_text="casa y casa",
        script_hint=None,
        source_document_id=sdid,
        candidate_results=candidate_results,
        sentences=[],
        uuid_to_candidate=uuid_to_candidate,
        user_id="test-user",
    )

    row = await db.get(TermProgressRow, ("test-user", "es", "casa"))
    assert row is not None
    assert row.exposure_count == 2


@pytest.mark.asyncio
async def test_same_term_across_two_sentences_counts_twice(db):
    """Same term in two separate CandidateSentenceResult entries → exposure_count == 2."""
    cand = _vocab_cand("casa", "casa")
    sdid = str(uuid.uuid4())
    uuid_to_candidate = {
        canonical_object_id("es", cand.type, cand.canonical_form): (cand.canonical_form, cand)
    }
    candidate_results = [
        CandidateSentenceResult(text="La casa.", candidates=[cand]),
        CandidateSentenceResult(text="Una casa.", candidates=[cand]),
    ]
    await persist_ingest(
        db,
        language="es",
        content_type="text",
        normalized_text="La casa. Una casa.",
        script_hint=None,
        source_document_id=sdid,
        candidate_results=candidate_results,
        sentences=[],
        uuid_to_candidate=uuid_to_candidate,
        user_id="test-user",
    )

    row = await db.get(TermProgressRow, ("test-user", "es", "casa"))
    assert row is not None
    assert row.exposure_count == 2


@pytest.mark.asyncio
async def test_multi_occurrence_source_lesson_ids_deduplicated(db):
    """Term appearing 3 times in one parse → exposure_count==3, obj_id in source_lesson_ids once."""
    cand = _vocab_cand("casa", "casa")
    obj_id = canonical_object_id("es", cand.type, cand.canonical_form)
    sdid = str(uuid.uuid4())
    uuid_to_candidate = {obj_id: (cand.canonical_form, cand)}
    candidate_results = [
        CandidateSentenceResult(text="casa.", candidates=[cand]),
        CandidateSentenceResult(text="casa.", candidates=[cand]),
        CandidateSentenceResult(text="casa.", candidates=[cand]),
    ]
    await persist_ingest(
        db,
        language="es",
        content_type="text",
        normalized_text="casa. casa. casa.",
        script_hint=None,
        source_document_id=sdid,
        candidate_results=candidate_results,
        sentences=[],
        uuid_to_candidate=uuid_to_candidate,
        user_id="test-user",
    )

    row = await db.get(TermProgressRow, ("test-user", "es", "casa"))
    assert row is not None
    assert row.exposure_count == 3
    assert row.source_lesson_ids.count(obj_id) == 1


@pytest.mark.asyncio
async def test_different_surface_forms_same_lemma_separate_rows(db):
    """Different surface forms of the same lemma create distinct TermProgressRow entries."""
    cand1 = _vocab_cand("corrió", "correr", canonical="correr:pret:3:Sing", type_="conjugation")
    cand2 = _vocab_cand("corría", "correr", canonical="correr:imperf:3:Sing", type_="conjugation")
    await persist_ingest(db, **_build_ingest_args([cand1, cand2], "es"))

    row1 = await db.get(TermProgressRow, ("test-user", "es", "corrió"))
    row2 = await db.get(TermProgressRow, ("test-user", "es", "corría"))
    assert row1 is not None
    assert row2 is not None
    assert row1.lemma == "correr"
    assert row2.lemma == "correr"
    assert row1.exposure_count == 1
    assert row2.exposure_count == 1
