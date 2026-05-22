"""Tests: GET /lesson/{object_id} user-aware enrichment.

Covers:
1. Default/anonymous user — no auth header, no mastery data → difficulty "easy".
2. Authenticated user with high mastery → difficulty "hard" in practice activities.
3. Cross-user isolation — user B cannot see user A's mastery data.
4. Related vocabulary in encountered_vocabulary via conjugation_of relation.
5. build_lesson is deterministic for identical enrichment input.
"""
from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.api.dependencies import get_current_user, get_db_session
from backend.lesson.enrichment import LessonEnrichmentContext
from backend.lesson.generators import build_lesson
from backend.main import app
from backend.models import (
    Base,
    CanonicalObjectRow,
    ObjectRelationRow,
    ParsedText,
    Sentence,
    SentenceObjectRow,
    TermProgressRow,
    UserKnowledgeRow,
)
from backend.schemas.lesson import EncounteredVocabularySummary
from backend.srs.knowledge import DEFAULT_USER_ID

# ── Constants ─────────────────────────────────────────────────────────────────

_VOCAB_OBJ_ID  = "aaaaaaaa-1111-2222-3333-444444444444"
_CONJ_OBJ_ID   = "bbbbbbbb-2222-3333-4444-555555555555"
_LEMMA_OBJ_ID  = "cccccccc-3333-4444-5555-666666666666"
_LANG          = "es"
_USER_A        = "lesson-user-alice"
_USER_B        = "lesson-user-bob"
_NOW           = datetime.now(UTC)

# Sentence-context test objects.
_CURR_SC_OBJ   = "11111111-aaaa-bbbb-cccc-dddddddddddd"
_CO_OBJ        = "22222222-aaaa-bbbb-cccc-dddddddddddd"
_CO_OBJ2       = "33333333-aaaa-bbbb-cccc-dddddddddddd"  # second co-occurring object
_PT_A          = "44444444-aaaa-bbbb-cccc-dddddddddddd"
_SENT_A        = "55555555-aaaa-bbbb-cccc-dddddddddddd"
_SENT_B        = "66666666-aaaa-bbbb-cccc-dddddddddddd"


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def db_engine(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/lesson_ua.db")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db(db_engine):
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session


@pytest_asyncio.fixture
async def session_factory(db_engine):
    return async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)


@asynccontextmanager
async def _as_user(sf, user_id: str):
    """ASGI test client scoped to *user_id*, using *sf* as the DB session factory."""
    async def _db():
        async with sf() as s:
            yield s

    app.dependency_overrides[get_db_session] = _db
    app.dependency_overrides[get_current_user] = lambda: user_id
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            yield ac
    finally:
        app.dependency_overrides.clear()


# ── Seed helpers ──────────────────────────────────────────────────────────────

def _make_vocab_row(obj_id: str = _VOCAB_OBJ_ID) -> CanonicalObjectRow:
    return CanonicalObjectRow(
        id=obj_id,
        language=_LANG,
        type="vocabulary",
        canonical_form="hablar",
        display_label="hablar",
        surface_forms=["hablar"],
        lesson_data={"lemma": "hablar", "pos": "VERB"},
    )


def _make_uk(user_id: str, obj_id: str, mastery: float) -> UserKnowledgeRow:
    return UserKnowledgeRow(
        user_id=user_id,
        object_id=obj_id,
        language=_LANG,
        fsrs_state=None,
        mastery_score=mastery,
        first_seen=_NOW,
        last_seen=_NOW,
        total_reviews=1,
        due_at=_NOW,
    )


# ── Tests ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_default_user_gets_easy_difficulty(db, session_factory):
    """No mastery data for the default user → all practice activities are 'easy'."""
    db.add(_make_vocab_row())
    await db.commit()

    async with _as_user(session_factory, DEFAULT_USER_ID) as client:
        resp = await client.get(f"/lesson/{_VOCAB_OBJ_ID}?language={_LANG}")

    assert resp.status_code == 200
    data = resp.json()
    activities = data.get("practice_activities", [])
    assert activities, "Expected at least one practice activity"
    assert all(a["difficulty"] == "easy" for a in activities)


@pytest.mark.asyncio
async def test_authenticated_user_mastery_tunes_difficulty(db, session_factory):
    """User with mastery_score ≥ 0.75 sees 'hard' practice activities."""
    db.add(_make_vocab_row())
    db.add(_make_uk(_USER_A, _VOCAB_OBJ_ID, mastery=0.85))
    await db.commit()

    async with _as_user(session_factory, _USER_A) as client:
        resp = await client.get(f"/lesson/{_VOCAB_OBJ_ID}?language={_LANG}")

    assert resp.status_code == 200
    data = resp.json()
    activities = data.get("practice_activities", [])
    assert activities
    assert all(a["difficulty"] == "hard" for a in activities)


@pytest.mark.asyncio
async def test_other_users_data_not_leaked(db, session_factory):
    """User B's lesson must not reflect user A's mastery score."""
    db.add(_make_vocab_row())
    db.add(_make_uk(_USER_A, _VOCAB_OBJ_ID, mastery=0.90))  # only user A has mastery
    await db.commit()

    async with _as_user(session_factory, _USER_B) as client:
        resp = await client.get(f"/lesson/{_VOCAB_OBJ_ID}?language={_LANG}")

    assert resp.status_code == 200
    data = resp.json()
    activities = data.get("practice_activities", [])
    assert activities
    # user B has no knowledge row → difficulty must be "easy"
    assert all(a["difficulty"] == "easy" for a in activities)


@pytest.mark.asyncio
async def test_term_progress_exposure_count_loaded(db, session_factory):
    """TermProgressRow exposure data is loaded (not leaked to another user)."""
    db.add(_make_vocab_row())
    # Seed a high-exposure TermProgressRow for user A only.
    db.add(TermProgressRow(
        user_id=_USER_A,
        language=_LANG,
        term="hablar",
        lemma="hablar",
        exposure_count=50,
        first_seen=_NOW,
        last_seen=_NOW,
        source_lesson_ids=[],
    ))
    await db.commit()

    # User B makes the request — they should NOT see user A's exposure data.
    async with _as_user(session_factory, _USER_B) as client:
        resp = await client.get(f"/lesson/{_VOCAB_OBJ_ID}?language={_LANG}")

    assert resp.status_code == 200
    # We can't inspect exposure_count directly in the response, but we can
    # confirm the route succeeds and difficulty is "easy" (no mastery for user B).
    data = resp.json()
    activities = data.get("practice_activities", [])
    assert all(a["difficulty"] == "easy" for a in activities)


@pytest.mark.asyncio
async def test_related_vocabulary_populated_via_relation(db, session_factory):
    """conjugation_of relation causes lemma to appear in encountered_vocabulary."""
    # Seed: conjugation object + vocabulary (lemma) object + relation.
    conj_obj = CanonicalObjectRow(
        id=_CONJ_OBJ_ID,
        language=_LANG,
        type="conjugation",
        canonical_form="hablar:present:indicative:1:Sing",
        display_label="hablo",
        surface_forms=["hablo"],
        lesson_data={
            "lemma": "hablar", "tense": "present", "mood": "indicative",
            "person": "1", "number": "Sing",
        },
    )
    lemma_obj = CanonicalObjectRow(
        id=_LEMMA_OBJ_ID,
        language=_LANG,
        type="vocabulary",
        canonical_form="hablar",
        display_label="hablar",
        surface_forms=["hablar"],
        lesson_data={"lemma": "hablar", "pos": "VERB", "gloss": "to speak"},
    )
    rel = ObjectRelationRow(
        id=str(uuid.uuid4()),
        source_id=_CONJ_OBJ_ID,
        target_id=_LEMMA_OBJ_ID,
        relation_type="conjugation_of",
    )
    db.add(conj_obj)
    db.add(lemma_obj)
    db.add(rel)
    await db.commit()

    async with _as_user(session_factory, _USER_A) as client:
        resp = await client.get(f"/lesson/{_CONJ_OBJ_ID}?language={_LANG}")

    assert resp.status_code == 200
    data = resp.json()
    vocab_list = data.get("encountered_vocabulary", [])
    assert len(vocab_list) == 1
    assert vocab_list[0]["form"] == "hablar"
    assert vocab_list[0]["gloss"] == "to speak"


@pytest.mark.asyncio
async def test_build_lesson_deterministic_with_enrichment():
    """build_lesson produces identical output for the same enrichment input."""
    enrichment = LessonEnrichmentContext(
        mastery_score=0.55,
        exposure_count=3,
        related_vocabulary=[
            EncounteredVocabularySummary(
                form="hablar", lemma="hablar", gloss="to speak", pos="VERB",
            )
        ],
    )

    kwargs = dict(
        object_id="test-det-uuid",
        obj_type="vocabulary",
        canonical_form="hablar",
        display_label="hablar",
        lesson_data={"lemma": "hablar", "pos": "VERB"},
        enrichment=enrichment,
    )

    result_a = build_lesson(**kwargs)
    result_b = build_lesson(**kwargs)

    assert result_a.model_dump_json() == result_b.model_dump_json()
    # Verify enrichment was used: medium difficulty (0.55 ≥ 0.4)
    assert all(a.difficulty == "medium" for a in result_a.practice_activities)
    # encountered_vocabulary populated
    assert len(result_a.encountered_vocabulary) == 1
    assert result_a.encountered_vocabulary[0].form == "hablar"


# ── Sentence-context vocabulary tests ─────────────────────────────────────────


def _make_co_vocab(obj_id: str, form: str, gloss: str) -> CanonicalObjectRow:
    return CanonicalObjectRow(
        id=obj_id,
        language=_LANG,
        type="vocabulary",
        canonical_form=form,
        display_label=form,
        surface_forms=[form],
        lesson_data={"lemma": form, "pos": "NOUN", "gloss": gloss},
    )


def _seed_sentence(
    parsed_text_id: str,
    sentence_id: str,
    sentence_text: str,
    object_ids: list[str],
) -> list:
    """Return ORM rows: ParsedText, Sentence, SentenceObjectRows."""
    rows: list = [
        ParsedText(id=parsed_text_id, language=_LANG, source_text=sentence_text),
        Sentence(id=sentence_id, parsed_text_id=parsed_text_id, position=0, text=sentence_text),
    ]
    for pos, oid in enumerate(object_ids):
        rows.append(SentenceObjectRow(sentence_id=sentence_id, object_id=oid, position=pos))
    return rows


@pytest.mark.asyncio
async def test_sentence_context_vocabulary_included(db, session_factory):
    """Object co-occurring in the same sentence appears in encountered_vocabulary."""
    curr = _make_vocab_row(_CURR_SC_OBJ)
    curr.canonical_form = "grande"
    curr.display_label = "grande"
    curr.lesson_data = {"lemma": "grande", "pos": "ADJ"}

    other = _make_co_vocab(_CO_OBJ, "casa", "house")

    for row in [curr, other] + _seed_sentence(
        _PT_A, _SENT_A, "La casa es grande.", [_CURR_SC_OBJ, _CO_OBJ]
    ):
        db.add(row)
    await db.commit()

    async with _as_user(session_factory, _USER_A) as client:
        resp = await client.get(f"/lesson/{_CURR_SC_OBJ}?language={_LANG}")

    assert resp.status_code == 200
    vocab_list = resp.json().get("encountered_vocabulary", [])
    forms = [v["form"] for v in vocab_list]
    assert "casa" in forms


@pytest.mark.asyncio
async def test_sentence_context_deduplication_across_sentences(db, session_factory):
    """Same co-occurring object in two sentences appears only once."""
    curr = _make_vocab_row(_CURR_SC_OBJ)
    curr.canonical_form = "grande"
    curr.display_label = "grande"
    curr.lesson_data = {"lemma": "grande", "pos": "ADJ"}

    other = _make_co_vocab(_CO_OBJ, "casa", "house")

    pt2_id = str(uuid.uuid4())
    sent2_id = str(uuid.uuid4())

    for row in (
        [curr, other]
        + _seed_sentence(_PT_A, _SENT_A, "La casa es grande.", [_CURR_SC_OBJ, _CO_OBJ])
        + _seed_sentence(pt2_id, sent2_id, "La casa grande.", [_CURR_SC_OBJ, _CO_OBJ])
    ):
        db.add(row)
    await db.commit()

    async with _as_user(session_factory, _USER_A) as client:
        resp = await client.get(f"/lesson/{_CURR_SC_OBJ}?language={_LANG}")

    assert resp.status_code == 200
    vocab_list = resp.json().get("encountered_vocabulary", [])
    forms = [v["form"] for v in vocab_list]
    assert forms.count("casa") == 1


@pytest.mark.asyncio
async def test_relation_and_sentence_context_merge_no_duplicates(db, session_factory):
    """Relation-linked object also in sentence → appears exactly once."""
    conj = CanonicalObjectRow(
        id=_CONJ_OBJ_ID,
        language=_LANG,
        type="conjugation",
        canonical_form="hablar:present:indicative:1:Sing",
        display_label="hablo",
        surface_forms=["hablo"],
        lesson_data={"lemma": "hablar"},
    )
    lemma = CanonicalObjectRow(
        id=_LEMMA_OBJ_ID,
        language=_LANG,
        type="vocabulary",
        canonical_form="hablar",
        display_label="hablar",
        surface_forms=["hablar"],
        lesson_data={"lemma": "hablar", "pos": "VERB", "gloss": "to speak"},
    )
    rel = ObjectRelationRow(
        id=str(uuid.uuid4()),
        source_id=_CONJ_OBJ_ID,
        target_id=_LEMMA_OBJ_ID,
        relation_type="conjugation_of",
    )
    # Both objects are also in the same sentence.
    for row in (
        [conj, lemma, rel]
        + _seed_sentence(_PT_A, _SENT_A, "Yo hablo.", [_CONJ_OBJ_ID, _LEMMA_OBJ_ID])
    ):
        db.add(row)
    await db.commit()

    async with _as_user(session_factory, _USER_A) as client:
        resp = await client.get(f"/lesson/{_CONJ_OBJ_ID}?language={_LANG}")

    assert resp.status_code == 200
    vocab_list = resp.json().get("encountered_vocabulary", [])
    forms = [v["form"] for v in vocab_list]
    assert forms.count("hablar") == 1


@pytest.mark.asyncio
async def test_sentence_context_other_user_term_progress_not_leaked(db, session_factory):
    """User B gets correct sentence-context vocabulary; user A's TermProgress is not injected."""
    curr = _make_vocab_row(_CURR_SC_OBJ)
    curr.canonical_form = "grande"
    curr.display_label = "grande"
    curr.lesson_data = {"lemma": "grande", "pos": "ADJ"}

    other = _make_co_vocab(_CO_OBJ, "casa", "house")

    # User A has high exposure to "casa" — must not affect user B's lesson.
    tp_a = TermProgressRow(
        user_id=_USER_A,
        language=_LANG,
        term="casa",
        lemma="casa",
        exposure_count=999,
        first_seen=_NOW,
        last_seen=_NOW,
        source_lesson_ids=[],
    )

    for row in [curr, other, tp_a] + _seed_sentence(
        _PT_A, _SENT_A, "La casa es grande.", [_CURR_SC_OBJ, _CO_OBJ]
    ):
        db.add(row)
    await db.commit()

    # User B has no knowledge rows — difficulty must be easy.
    async with _as_user(session_factory, _USER_B) as client:
        resp = await client.get(f"/lesson/{_CURR_SC_OBJ}?language={_LANG}")

    assert resp.status_code == 200
    data = resp.json()
    # Sentence-context vocabulary still available to user B.
    forms = [v["form"] for v in data.get("encountered_vocabulary", [])]
    assert "casa" in forms
    # User B has no mastery → easy difficulty.
    assert all(a["difficulty"] == "easy" for a in data.get("practice_activities", []))


@pytest.mark.asyncio
async def test_build_lesson_without_enrichment_empty_vocabulary():
    """Plugin fallback path (no enrichment) yields empty encountered_vocabulary."""
    result = build_lesson(
        object_id="no-enrichment-id",
        obj_type="vocabulary",
        canonical_form="mesa",
        display_label="mesa",
        lesson_data={"lemma": "mesa", "pos": "NOUN"},
        # enrichment omitted → None
    )
    assert result.encountered_vocabulary == []
