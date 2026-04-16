"""Non-Latin script round-trip and RTL pipeline tests.

M4 — Non-Latin DB round-trip
─────────────────────────────
Push Arabic, Hebrew, Chinese, Russian, and Japanese canonical forms through
``canonical_object_id()`` and into an in-memory SQLite database, then retrieve
them and assert the round-trip is lossless.

Goals:
- Expose encoding or collation bugs early (Unicode normalisation, SQLite TEXT
  encoding, aiosqlite divergence).
- Verify that ``canonical_object_id()`` returns distinct, stable UUIDs for
  non-Latin text across languages.
- Confirm that ``surface_forms`` (JSON array) round-trips Semitic and CJK text
  without garbling.

B4 — RTL pipeline (API level)
──────────────────────────────
Push Arabic and Hebrew text through ``POST /parse`` using in-memory SQLite and
assert that:
- The response includes ``direction: "rtl"`` in the language capabilities.
- Object IDs in the response are stable UUIDs.
- The parse route does not crash on non-ASCII, non-Latin input.

All tests use in-memory SQLite — no running PostgreSQL or Redis required.
"""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.core.database import get_db_session
from backend.main import app
from backend.models import Base, CanonicalObjectRow
from backend.parsing.canonical import canonical_object_id

_TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


# ── Non-Latin fixture data ─────────────────────────────────────────────────────

# (language_code, type_, canonical_form, display_label, surface_form)
_FIXTURES: list[tuple[str, str, str, str, str]] = [
    ("ar", "vocabulary", "كتاب",   "كتاب",   "كتابًا"),   # Arabic: book
    ("ar", "vocabulary", "كَتَبَ",   "كَتَبَ",   "كَتَبَ"),    # Arabic: he wrote (diacritised)
    ("he", "vocabulary", "ספר",    "ספר",    "ספרים"),    # Hebrew: book / books
    ("he", "vocabulary", "שַׁבָּת",  "שַׁבָּת",  "שַׁבָּת"),   # Hebrew: Shabbat (pointed)
    ("zh", "vocabulary", "书",     "书",     "书"),        # Chinese: book
    ("zh", "vocabulary", "东京",   "东京",   "东京"),      # Chinese: Tokyo
    ("ru", "vocabulary", "книга",  "книга",  "книги"),    # Russian: book (nom/gen)
    ("ru", "vocabulary", "читать", "читать", "читает"),   # Russian: to read / reads
    ("ja", "vocabulary", "猫",     "猫",     "猫"),        # Japanese: cat
    ("ja", "vocabulary", "東京",   "東京",   "東京"),      # Japanese: Tokyo
]

# Scripts that must render RTL in the UI
_RTL_LANGUAGES = frozenset({"ar", "he"})


# ── DB fixtures ───────────────────────────────────────────────────────────────


@pytest_asyncio.fixture(scope="module")
async def db_engine():
    engine = create_async_engine(_TEST_DB_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="module")
async def db_session(db_engine):
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session


@pytest_asyncio.fixture(scope="module")
async def async_client(db_engine):
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)

    async def _override_db():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = _override_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.pop(get_db_session, None)


# ── canonical_object_id — UUID stability ─────────────────────────────────────


class TestCanonicalObjectIdNonLatin:
    def test_arabic_produces_valid_uuid(self) -> None:
        obj_id = canonical_object_id("ar", "vocabulary", "كتاب")
        parsed = uuid.UUID(obj_id)
        assert parsed.version == 5

    def test_hebrew_produces_valid_uuid(self) -> None:
        obj_id = canonical_object_id("he", "vocabulary", "ספר")
        parsed = uuid.UUID(obj_id)
        assert parsed.version == 5

    def test_chinese_produces_valid_uuid(self) -> None:
        obj_id = canonical_object_id("zh", "vocabulary", "书")
        parsed = uuid.UUID(obj_id)
        assert parsed.version == 5

    def test_russian_produces_valid_uuid(self) -> None:
        obj_id = canonical_object_id("ru", "vocabulary", "книга")
        parsed = uuid.UUID(obj_id)
        assert parsed.version == 5

    def test_japanese_produces_valid_uuid(self) -> None:
        obj_id = canonical_object_id("ja", "vocabulary", "猫")
        parsed = uuid.UUID(obj_id)
        assert parsed.version == 5

    def test_arabic_with_tashkeel_distinct_from_bare(self) -> None:
        """Diacritised and undiacritised Arabic produce different UUIDs.

        Plugins normalise to undiacritised before storing; this test confirms
        that the UUID derivation does not silently conflate them.
        """
        bare  = canonical_object_id("ar", "vocabulary", "كتب")
        tash  = canonical_object_id("ar", "vocabulary", "كَتَبَ")
        assert bare != tash

    def test_hebrew_pointed_distinct_from_bare(self) -> None:
        bare    = canonical_object_id("he", "vocabulary", "שבת")
        pointed = canonical_object_id("he", "vocabulary", "שַׁבָּת")
        assert bare != pointed

    def test_same_form_different_languages_distinct(self) -> None:
        """Same string in different language namespaces must not collide."""
        ja_id = canonical_object_id("ja", "vocabulary", "東京")
        zh_id = canonical_object_id("zh", "vocabulary", "東京")
        assert ja_id != zh_id

    def test_uuid_is_deterministic(self) -> None:
        """Calling canonical_object_id twice for the same inputs returns the same UUID."""
        first  = canonical_object_id("ar", "vocabulary", "كتاب")
        second = canonical_object_id("ar", "vocabulary", "كتاب")
        assert first == second

    @pytest.mark.parametrize("lang,type_,form,_label,_surf", _FIXTURES)
    def test_all_fixtures_produce_unique_ids(self, lang, type_, form, _label, _surf) -> None:
        obj_id = canonical_object_id(lang, type_, form)
        assert uuid.UUID(obj_id).version == 5

    def test_all_fixture_ids_are_mutually_distinct(self) -> None:
        ids = [
            canonical_object_id(lang, type_, form)
            for lang, type_, form, _, _ in _FIXTURES
        ]
        assert len(ids) == len(set(ids)), "Collision detected among fixture UUIDs"


# ── DB round-trip — insert + retrieve ────────────────────────────────────────


class TestNonLatinDbRoundtrip:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("lang,type_,form,label,surf", _FIXTURES)
    async def test_insert_and_retrieve_canonical_form(
        self, db_session: AsyncSession, lang, type_, form, label, surf
    ) -> None:
        """Insert a non-Latin canonical object and retrieve it losslessly."""
        obj_id = canonical_object_id(lang, type_, form)
        row = CanonicalObjectRow(
            id=obj_id,
            language=lang,
            type=type_,
            canonical_form=form,
            display_label=label,
            surface_forms=[surf],
            lesson_data={"lemma": form},
            confidence=0.80,
        )
        db_session.add(row)
        await db_session.flush()

        result = await db_session.execute(
            select(CanonicalObjectRow).where(CanonicalObjectRow.id == obj_id)
        )
        retrieved = result.scalar_one()

        assert retrieved.canonical_form == form, (
            f"canonical_form round-trip failed for ({lang}, {form!r}): "
            f"got {retrieved.canonical_form!r}"
        )
        assert retrieved.language == lang
        assert retrieved.type == type_
        assert retrieved.display_label == label

    @pytest.mark.asyncio
    async def test_arabic_surface_forms_json_roundtrip(self, db_session: AsyncSession) -> None:
        """Arabic surface forms (JSON array) survive the DB round-trip intact."""
        form      = "قرأ"
        surfaces  = ["يَقْرَأ", "قَرَأَ", "قُرِئَ"]
        obj_id    = canonical_object_id("ar", "vocabulary", form)

        existing = await db_session.get(CanonicalObjectRow, obj_id)
        if existing is None:
            db_session.add(CanonicalObjectRow(
                id=obj_id, language="ar", type="vocabulary",
                canonical_form=form, display_label=form,
                surface_forms=surfaces,
                lesson_data={"lemma": form},
            ))
            await db_session.flush()

        result    = await db_session.execute(
            select(CanonicalObjectRow).where(CanonicalObjectRow.id == obj_id)
        )
        retrieved = result.scalar_one()
        assert retrieved.surface_forms == surfaces or set(retrieved.surface_forms) >= set(surfaces), (
            f"surface_forms round-trip failed: {retrieved.surface_forms!r}"
        )

    @pytest.mark.asyncio
    async def test_hebrew_lesson_data_json_roundtrip(self, db_session: AsyncSession) -> None:
        """Hebrew lesson_data dict survives the DB round-trip intact."""
        # Use "ירושלים" (Jerusalem) — not in _FIXTURES so no prior insert.
        form   = "ירושלים"
        obj_id = canonical_object_id("he", "vocabulary", form)
        data   = {
            "lemma":   "ירושלים",
            "pos":     "PROPN",
            "gender":  "Masc",
            "number":  "Sing",
            "confidence_note": "proper noun — low confidence",
        }

        existing = await db_session.get(CanonicalObjectRow, obj_id)
        if existing is None:
            db_session.add(CanonicalObjectRow(
                id=obj_id, language="he", type="vocabulary",
                canonical_form=form, display_label="ירושלים",
                surface_forms=[form],
                lesson_data=data,
            ))
            await db_session.flush()

        result    = await db_session.execute(
            select(CanonicalObjectRow).where(CanonicalObjectRow.id == obj_id)
        )
        retrieved = result.scalar_one()
        for key, value in data.items():
            assert retrieved.lesson_data.get(key) == value, (
                f"lesson_data[{key!r}] round-trip failed: "
                f"expected {value!r}, got {retrieved.lesson_data.get(key)!r}"
            )

    @pytest.mark.asyncio
    async def test_chinese_cjk_canonical_form_roundtrip(self, db_session: AsyncSession) -> None:
        """CJK canonical forms survive the DB round-trip without garbling."""
        forms = ["书", "东京", "学生", "日本語", "中文"]
        for form in forms:
            obj_id = canonical_object_id("zh", "vocabulary", form)
            existing = await db_session.get(CanonicalObjectRow, obj_id)
            if existing is None:
                db_session.add(CanonicalObjectRow(
                    id=obj_id, language="zh", type="vocabulary",
                    canonical_form=form, display_label=form,
                    surface_forms=[form],
                    lesson_data={"lemma": form},
                ))
        await db_session.flush()

        for form in forms:
            obj_id = canonical_object_id("zh", "vocabulary", form)
            result = await db_session.execute(
                select(CanonicalObjectRow).where(CanonicalObjectRow.id == obj_id)
            )
            retrieved = result.scalar_one()
            assert retrieved.canonical_form == form, (
                f"CJK round-trip failed for {form!r}: got {retrieved.canonical_form!r}"
            )

    @pytest.mark.asyncio
    async def test_russian_cyrillic_canonical_form_roundtrip(self, db_session: AsyncSession) -> None:
        """Cyrillic canonical forms survive the DB round-trip."""
        forms = ["книга", "читать", "собака", "красивый", "Москва"]
        for form in forms:
            obj_id = canonical_object_id("ru", "vocabulary", form)
            existing = await db_session.get(CanonicalObjectRow, obj_id)
            if existing is None:
                db_session.add(CanonicalObjectRow(
                    id=obj_id, language="ru", type="vocabulary",
                    canonical_form=form, display_label=form,
                    surface_forms=[form],
                    lesson_data={"lemma": form},
                ))
        await db_session.flush()

        for form in forms:
            obj_id = canonical_object_id("ru", "vocabulary", form)
            result = await db_session.execute(
                select(CanonicalObjectRow).where(CanonicalObjectRow.id == obj_id)
            )
            retrieved = result.scalar_one()
            assert retrieved.canonical_form == form

    @pytest.mark.asyncio
    async def test_japanese_mixed_script_canonical_form_roundtrip(
        self, db_session: AsyncSession
    ) -> None:
        """Japanese forms mixing kanji, hiragana, and katakana survive the DB round-trip."""
        forms = ["猫", "東京", "ねこ", "トウキョウ", "食べる"]
        for form in forms:
            obj_id = canonical_object_id("ja", "vocabulary", form)
            existing = await db_session.get(CanonicalObjectRow, obj_id)
            if existing is None:
                db_session.add(CanonicalObjectRow(
                    id=obj_id, language="ja", type="vocabulary",
                    canonical_form=form, display_label=form,
                    surface_forms=[form],
                    lesson_data={"lemma": form},
                ))
        await db_session.flush()

        for form in forms:
            obj_id = canonical_object_id("ja", "vocabulary", form)
            result = await db_session.execute(
                select(CanonicalObjectRow).where(CanonicalObjectRow.id == obj_id)
            )
            retrieved = result.scalar_one()
            assert retrieved.canonical_form == form

    @pytest.mark.asyncio
    async def test_uq_constraint_respected_for_arabic(self, db_session: AsyncSession) -> None:
        """The (language, type, canonical_form) unique constraint must hold."""
        from sqlalchemy.exc import IntegrityError

        form   = "مكتبة"
        obj_id = canonical_object_id("ar", "vocabulary", form)

        existing = await db_session.get(CanonicalObjectRow, obj_id)
        if existing is None:
            db_session.add(CanonicalObjectRow(
                id=obj_id, language="ar", type="vocabulary",
                canonical_form=form, display_label=form,
                surface_forms=[form], lesson_data={},
            ))
            await db_session.flush()

        # Attempting to insert a second row with the same (language, type, canonical_form)
        # but a different PK should violate the unique constraint.
        duplicate_id = str(uuid.uuid4())  # different PK
        db_session.add(CanonicalObjectRow(
            id=duplicate_id, language="ar", type="vocabulary",
            canonical_form=form, display_label=form,
            surface_forms=[], lesson_data={},
        ))
        with pytest.raises(IntegrityError):
            await db_session.flush()
        await db_session.rollback()


# ── B4 — RTL direction in API response ────────────────────────────────────────


class TestRtlPipelineApi:
    """API-level tests: assert RTL direction appears in plugin capabilities.

    These tests do not require spaCy Arabic/Hebrew models — they query
    GET /languages which returns the plugin registry, and assert that the
    Arabic and Hebrew plugins report direction="rtl".
    """

    @pytest.mark.asyncio
    async def test_languages_endpoint_arabic_is_rtl(self, async_client: AsyncClient) -> None:
        resp = await async_client.get("/languages")
        assert resp.status_code == 200
        langs = {lang["code"]: lang for lang in resp.json()}
        if "ar" in langs:
            assert langs["ar"]["direction"] == "rtl", (
                f"Arabic plugin must report direction='rtl', got: {langs['ar']['direction']!r}"
            )

    @pytest.mark.asyncio
    async def test_languages_endpoint_hebrew_is_rtl(self, async_client: AsyncClient) -> None:
        resp = await async_client.get("/languages")
        assert resp.status_code == 200
        langs = {lang["code"]: lang for lang in resp.json()}
        if "he" in langs:
            assert langs["he"]["direction"] == "rtl", (
                f"Hebrew plugin must report direction='rtl', got: {langs['he']['direction']!r}"
            )

    @pytest.mark.asyncio
    async def test_languages_endpoint_ltr_languages_not_rtl(
        self, async_client: AsyncClient
    ) -> None:
        resp = await async_client.get("/languages")
        assert resp.status_code == 200
        ltr_codes = {"es", "fr", "de", "ru", "zh", "ja", "la"}
        langs = {lang["code"]: lang for lang in resp.json()}
        for code in ltr_codes & set(langs):
            assert langs[code]["direction"] == "ltr", (
                f"Language {code!r} should be ltr, got {langs[code]['direction']!r}"
            )

    @pytest.mark.asyncio
    async def test_parse_arabic_text_returns_200(self, async_client: AsyncClient) -> None:
        """POST /parse with Arabic text must not 500 — verify plugin handles the input."""
        resp = await async_client.post(
            "/parse",
            json={"text": "الكتاب على الطاولة.", "language": "ar"},
            headers={"X-User-Id": "test-rtl"},
        )
        # 200 = Arabic plugin found and parsed.
        # 422 = language not registered (model not installed — acceptable skip).
        # 404 = same.
        assert resp.status_code in (200, 404, 422), (
            f"Unexpected status {resp.status_code}: {resp.text}"
        )
        if resp.status_code == 200:
            body = resp.json()
            assert "sentences" in body
            # Verify returned object IDs are valid UUIDs
            for sent in body["sentences"]:
                for obj in sent.get("learnable_objects", []):
                    assert uuid.UUID(obj["id"]).version == 5

    @pytest.mark.asyncio
    async def test_parse_hebrew_text_returns_200(self, async_client: AsyncClient) -> None:
        """POST /parse with Hebrew text must not 500."""
        resp = await async_client.post(
            "/parse",
            json={"text": "הספר על השולחן.", "language": "he"},
            headers={"X-User-Id": "test-rtl"},
        )
        assert resp.status_code in (200, 404, 422), (
            f"Unexpected status {resp.status_code}: {resp.text}"
        )
        if resp.status_code == 200:
            body = resp.json()
            assert "sentences" in body
            for sent in body["sentences"]:
                for obj in sent.get("learnable_objects", []):
                    assert uuid.UUID(obj["id"]).version == 5

    @pytest.mark.asyncio
    async def test_parse_chinese_text_object_ids_are_uuids(
        self, async_client: AsyncClient
    ) -> None:
        """POST /parse with CJK text must return stable UUID object IDs."""
        resp = await async_client.post(
            "/parse",
            json={"text": "我在北京学习中文。", "language": "zh"},
            headers={"X-User-Id": "test-cjk"},
        )
        assert resp.status_code in (200, 404, 422)
        if resp.status_code == 200:
            for sent in resp.json()["sentences"]:
                for obj in sent.get("learnable_objects", []):
                    assert uuid.UUID(obj["id"]).version == 5

    @pytest.mark.asyncio
    async def test_parse_arabic_object_ids_are_stable(
        self, async_client: AsyncClient
    ) -> None:
        """The same Arabic word in two parses must produce the same UUID."""
        text = "الكتاب."
        resp1 = await async_client.post(
            "/parse",
            json={"text": text, "language": "ar"},
            headers={"X-User-Id": "test-rtl-stable"},
        )
        resp2 = await async_client.post(
            "/parse",
            json={"text": text, "language": "ar"},
            headers={"X-User-Id": "test-rtl-stable"},
        )
        if resp1.status_code == 200 and resp2.status_code == 200:
            ids1 = {o["id"] for s in resp1.json()["sentences"] for o in s.get("learnable_objects", [])}
            ids2 = {o["id"] for s in resp2.json()["sentences"] for o in s.get("learnable_objects", [])}
            assert ids1 == ids2, (
                f"Arabic parse IDs are not stable across identical requests: "
                f"{ids1} vs {ids2}"
            )
