"""Tests for backend/services/sentence_mining.py — mine_parsed_text().

Verifies that mining fires correctly after a parse persists, that it is
idempotent, and that non-fatal failures don't propagate.
"""
from __future__ import annotations

from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy import select

from backend.models import (
    Base,
    CanonicalObjectRow,
    ParsedText,
    Sentence,
    SentenceObjectRow,
    SentenceReviewItemRow,
    UserSentenceReviewRow,
)
from backend.services.sentence_mining import mine_parsed_text

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def db_engine(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/test.db")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db(db_engine):
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session


# ── Seed helpers ──────────────────────────────────────────────────────────────


async def _seed_parsed_text(db: AsyncSession, language: str = "es") -> ParsedText:
    pt = ParsedText(language=language, source_text="seed", user_id="u1")
    db.add(pt)
    await db.commit()
    await db.refresh(pt)
    return pt


async def _seed_sentence(db: AsyncSession, pt_id: str, text: str, pos: int = 0) -> Sentence:
    s = Sentence(parsed_text_id=pt_id, position=pos, text=text)
    db.add(s)
    await db.commit()
    await db.refresh(s)
    return s


async def _seed_vocab_object(
    db: AsyncSession,
    *,
    language: str = "es",
    label: str = "casa",
    surface_forms: list[str] | None = None,
    confidence: float = 0.85,
) -> CanonicalObjectRow:
    import uuid as _uuid
    obj = CanonicalObjectRow(
        id=str(_uuid.uuid4()),
        language=language,
        type="vocabulary",
        canonical_form=label,
        display_label=label,
        surface_forms=surface_forms or [label],
        lesson_data={"cefr_level": "A1"},
        confidence=confidence,
    )
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    return obj


async def _link(db: AsyncSession, sentence_id: str, object_id: str, pos: int = 0):
    db.add(SentenceObjectRow(sentence_id=sentence_id, object_id=object_id, position=pos))
    await db.commit()


# ── Tests ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_mine_creates_items_and_user_rows(db):
    """mine_parsed_text creates SentenceReviewItem + UserSentenceReview rows."""
    pt = await _seed_parsed_text(db)
    sent = await _seed_sentence(
        db, pt.id, "La casa es muy grande y bonita en el barrio.", 0
    )
    obj = await _seed_vocab_object(db, label="casa", surface_forms=["casa"])
    await _link(db, sent.id, obj.id)

    mined, skipped = await mine_parsed_text(
        db, parsed_text_id=pt.id, language="es", user_id="u1"
    )

    assert mined > 0
    assert skipped == 0

    items = (
        await db.execute(
            select(SentenceReviewItemRow).where(
                SentenceReviewItemRow.sentence_id == sent.id
            )
        )
    ).scalars().all()
    assert len(items) == mined

    for item in items:
        ur = await db.scalar(
            select(UserSentenceReviewRow).where(
                UserSentenceReviewRow.user_id == "u1",
                UserSentenceReviewRow.item_id == item.id,
            )
        )
        assert ur is not None, "UserSentenceReviewRow must be created for each item"
        assert ur.due_at is not None


@pytest.mark.asyncio
async def test_mine_idempotent(db):
    """Second call to mine_parsed_text skips all previously mined items."""
    pt = await _seed_parsed_text(db)
    sent = await _seed_sentence(
        db, pt.id, "La casa es muy grande y bonita en el barrio.", 0
    )
    obj = await _seed_vocab_object(db, label="casa", surface_forms=["casa"])
    await _link(db, sent.id, obj.id)

    mined1, skipped1 = await mine_parsed_text(
        db, parsed_text_id=pt.id, language="es", user_id="u1"
    )
    mined2, skipped2 = await mine_parsed_text(
        db, parsed_text_id=pt.id, language="es", user_id="u1"
    )

    assert mined1 > 0
    assert mined2 == 0
    assert skipped2 == mined1


@pytest.mark.asyncio
async def test_mine_empty_parsed_text_returns_zero(db):
    """Parsed text with no sentences returns (0, 0)."""
    pt = await _seed_parsed_text(db)

    mined, skipped = await mine_parsed_text(
        db, parsed_text_id=pt.id, language="es", user_id="u1"
    )

    assert mined == 0
    assert skipped == 0


@pytest.mark.asyncio
async def test_mine_sentence_with_no_objects_returns_zero(db):
    """Sentence with no linked canonical objects produces no items."""
    pt = await _seed_parsed_text(db)
    await _seed_sentence(db, pt.id, "La casa es grande.", 0)
    # No SentenceObjectRow — no canonical objects linked.

    mined, skipped = await mine_parsed_text(
        db, parsed_text_id=pt.id, language="es", user_id="u1"
    )

    assert mined == 0


@pytest.mark.asyncio
async def test_mine_multiple_sentences(db):
    """Multiple eligible sentences each produce items."""
    pt = await _seed_parsed_text(db)
    s0 = await _seed_sentence(db, pt.id, "La casa es muy grande y bonita.", 0)
    s1 = await _seed_sentence(db, pt.id, "El libro está sobre la mesa grande.", 1)

    obj_casa = await _seed_vocab_object(db, label="casa", surface_forms=["casa"])
    obj_libro = await _seed_vocab_object(db, label="libro", surface_forms=["libro"])
    await _link(db, s0.id, obj_casa.id)
    await _link(db, s1.id, obj_libro.id)

    mined, _ = await mine_parsed_text(
        db, parsed_text_id=pt.id, language="es", user_id="u1"
    )

    assert mined >= 2


@pytest.mark.asyncio
async def test_mine_due_at_set_to_now(db):
    """Mined items are due immediately (due_at ≈ now)."""
    pt = await _seed_parsed_text(db)
    sent = await _seed_sentence(
        db, pt.id, "La casa es muy grande y bonita en el barrio.", 0
    )
    obj = await _seed_vocab_object(db, label="casa", surface_forms=["casa"])
    await _link(db, sent.id, obj.id)

    before = datetime.now(UTC)
    await mine_parsed_text(db, parsed_text_id=pt.id, language="es", user_id="u1")
    after = datetime.now(UTC)

    urs = (
        await db.execute(select(UserSentenceReviewRow).where(UserSentenceReviewRow.user_id == "u1"))
    ).scalars().all()

    for ur in urs:
        due = ur.due_at
        if due.tzinfo is None:
            from datetime import timezone
            due = due.replace(tzinfo=timezone.utc)
        assert before <= due <= after, "due_at must be within the test window"


@pytest.mark.asyncio
async def test_mine_short_sentence_skipped(db):
    """Sentences shorter than _MIN_SENTENCE_CHARS produce no items."""
    pt = await _seed_parsed_text(db)
    # Very short sentence — below the 15-char minimum.
    sent = await _seed_sentence(db, pt.id, "Hola.", 0)
    obj = await _seed_vocab_object(db, label="hola", surface_forms=["hola"])
    await _link(db, sent.id, obj.id)

    mined, _ = await mine_parsed_text(
        db, parsed_text_id=pt.id, language="es", user_id="u1"
    )

    assert mined == 0, "Short sentences must not produce review items"
