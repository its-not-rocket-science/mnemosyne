"""Tests for the etymology enrichment layer.

Covers:
- EtymologyEntry model construction and to_lesson_data()
- EtymologyStore.get() — hit, miss, case normalisation
- DEFAULT_STORE — seeded words across all supported languages
- apply_etymology() — DB-level enrichment with SQLite fixture
- RTL/CJK scripts — Hebrew, Arabic, Japanese, Chinese
- Silent miss degradation — no entry → no crash
"""
from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.dictionary.etymology import (
    DEFAULT_STORE,
    EtymologyEntry,
    EtymologyStore,
    apply_etymology,
)
from backend.models import Base, CanonicalObjectRow
from backend.parsing.canonical import canonical_object_id


# ── EtymologyEntry ────────────────────────────────────────────────────────────

class TestEtymologyEntry:
    def test_minimal_construction(self):
        e = EtymologyEntry(language="es", lemma="casa", origin_summary="From Latin casa.")
        assert e.language == "es"
        assert e.lemma == "casa"
        assert e.roots == []
        assert e.cognates == []
        assert e.semantic_shift is None
        assert e.confidence == 1.0
        assert e.source_type == "curated"

    def test_full_construction(self):
        e = EtymologyEntry(
            language="la", lemma="persona",
            origin_summary="From Etruscan phersu.",
            roots=["Etruscan phersu"],
            cognates=["English person"],
            semantic_shift="mask → individual",
            confidence=0.95,
            source_type="curated",
        )
        assert e.roots == ["Etruscan phersu"]
        assert e.cognates == ["English person"]
        assert e.semantic_shift == "mask → individual"
        assert e.confidence == 0.95

    def test_to_lesson_data_minimal(self):
        e = EtymologyEntry(language="es", lemma="casa", origin_summary="From Latin casa.")
        d = e.to_lesson_data()
        assert d["origin_summary"] == "From Latin casa."
        assert d["confidence"] == 1.0
        assert d["source_type"] == "curated"
        assert "roots" not in d
        assert "cognates" not in d
        assert "semantic_shift" not in d

    def test_to_lesson_data_full(self):
        e = EtymologyEntry(
            language="la", lemma="persona",
            origin_summary="From Etruscan phersu.",
            roots=["Etruscan phersu"],
            cognates=["English person"],
            semantic_shift="mask → individual",
        )
        d = e.to_lesson_data()
        assert d["roots"] == ["Etruscan phersu"]
        assert d["cognates"] == ["English person"]
        assert d["semantic_shift"] == "mask → individual"


# ── EtymologyStore ────────────────────────────────────────────────────────────

class TestEtymologyStore:
    def _make_entry(self, lang, lemma):
        return EtymologyEntry(language=lang, lemma=lemma, origin_summary=f"Origin of {lemma}.")

    def test_get_hit(self):
        store = EtymologyStore([self._make_entry("es", "tiempo")])
        e = store.get("es", "tiempo")
        assert e is not None
        assert e.lemma == "tiempo"

    def test_get_miss_wrong_language(self):
        store = EtymologyStore([self._make_entry("es", "tiempo")])
        assert store.get("fr", "tiempo") is None

    def test_get_miss_unknown_lemma(self):
        store = EtymologyStore([self._make_entry("es", "tiempo")])
        assert store.get("es", "desconocido") is None

    def test_case_normalisation(self):
        store = EtymologyStore([self._make_entry("de", "Kindergarten")])
        # stored as lowercase key; lookup is case-insensitive
        assert store.get("de", "kindergarten") is not None
        assert store.get("de", "KINDERGARTEN") is not None
        assert store.get("de", "Kindergarten") is not None

    def test_len(self):
        store = EtymologyStore([
            self._make_entry("es", "tiempo"),
            self._make_entry("fr", "château"),
        ])
        assert len(store) == 2

    def test_add_overwrites(self):
        store = EtymologyStore()
        store.add(EtymologyEntry(language="es", lemma="tiempo", origin_summary="v1"))
        store.add(EtymologyEntry(language="es", lemma="tiempo", origin_summary="v2"))
        assert store.get("es", "tiempo").origin_summary == "v2"
        assert len(store) == 1


# ── DEFAULT_STORE coverage ────────────────────────────────────────────────────

class TestDefaultStore:
    @pytest.mark.parametrize("lang,lemma", [
        ("es", "tiempo"),
        ("es", "amigo"),
        ("fr", "naïf"),
        ("fr", "château"),
        ("de", "Schadenfreude"),
        ("de", "Kindergarten"),
        ("it", "ciao"),
        ("it", "piano"),
        ("pt", "saudade"),
        ("pt", "fado"),
        ("ru", "тоска"),
        ("ru", "правда"),
        ("ar", "قلم"),
        ("ar", "كتاب"),
        ("zh", "茶"),
        ("zh", "道"),
        ("he", "שלום"),
        ("he", "אמן"),
        ("ja", "木漏れ日"),
        ("ja", "勉強"),
        ("grc", "λόγος"),
        ("grc", "ἀγάπη"),
        ("la", "persona"),
        ("la", "sinister"),
    ])
    def test_seeded_word_present(self, lang, lemma):
        e = DEFAULT_STORE.get(lang, lemma)
        assert e is not None, f"No etymology for ({lang!r}, {lemma!r})"
        assert e.origin_summary, "origin_summary must not be empty"
        assert e.confidence > 0
        assert e.source_type == "curated"

    def test_missing_word_returns_none(self):
        assert DEFAULT_STORE.get("es", "xyz_nonexistent_word") is None

    def test_default_store_nonempty(self):
        assert len(DEFAULT_STORE) > 0


# ── RTL and CJK script rendering ─────────────────────────────────────────────

class TestScriptRendering:
    """Verify that RTL and CJK entries have valid non-empty text fields."""

    def test_arabic_entry_text_valid(self):
        e = DEFAULT_STORE.get("ar", "قلم")
        assert e is not None
        # All text fields should be valid Unicode strings
        assert isinstance(e.origin_summary, str)
        assert len(e.origin_summary) > 0
        # Roots may reference Arabic script
        for root in e.roots:
            assert isinstance(root, str)

    def test_hebrew_entry_text_valid(self):
        e = DEFAULT_STORE.get("he", "שלום")
        assert e is not None
        assert isinstance(e.origin_summary, str)
        assert len(e.origin_summary) > 0

    def test_chinese_entry_text_valid(self):
        e = DEFAULT_STORE.get("zh", "茶")
        assert e is not None
        assert isinstance(e.origin_summary, str)
        assert len(e.origin_summary) > 0
        d = e.to_lesson_data()
        assert isinstance(d["origin_summary"], str)

    def test_japanese_entry_text_valid(self):
        e = DEFAULT_STORE.get("ja", "木漏れ日")
        assert e is not None
        assert isinstance(e.origin_summary, str)
        assert len(e.origin_summary) > 0

    def test_to_lesson_data_roundtrip_rtl(self):
        e = DEFAULT_STORE.get("ar", "كتاب")
        assert e is not None
        d = e.to_lesson_data()
        assert isinstance(d["origin_summary"], str)
        assert d["source_type"] == "curated"

    def test_to_lesson_data_roundtrip_cjk(self):
        e = DEFAULT_STORE.get("zh", "道")
        assert e is not None
        d = e.to_lesson_data()
        assert isinstance(d["origin_summary"], str)
        assert "roots" in d


# ── apply_etymology (DB-level) ────────────────────────────────────────────────

@pytest_asyncio.fixture
async def async_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


def _make_row(language: str, canonical_form: str, lesson_data: dict | None = None):
    row = CanonicalObjectRow()
    row.id = canonical_object_id(language, "vocabulary", canonical_form)
    row.language = language
    row.type = "vocabulary"
    row.canonical_form = canonical_form
    row.display_label = canonical_form
    row.lesson_data = {"lemma": canonical_form, **(lesson_data or {})}
    return row


class TestApplyEtymology:
    @pytest.mark.asyncio
    async def test_seeded_word_gets_etymology(self, async_db: AsyncSession):
        row = _make_row("es", "tiempo")
        async_db.add(row)
        await async_db.commit()

        await apply_etymology(async_db, [row.id])

        await async_db.refresh(row)
        etym = (row.lesson_data or {}).get("etymology")
        assert etym is not None
        assert "origin_summary" in etym
        assert isinstance(etym["origin_summary"], str)
        assert len(etym["origin_summary"]) > 0

    @pytest.mark.asyncio
    async def test_missing_word_degrades_silently(self, async_db: AsyncSession):
        row = _make_row("es", "desconocido_xyz")
        async_db.add(row)
        await async_db.commit()

        # Should not raise
        await apply_etymology(async_db, [row.id])

        await async_db.refresh(row)
        ld = row.lesson_data or {}
        assert ld.get("etymology") is None
        assert ld.get("etymology_attempted") is True

    @pytest.mark.asyncio
    async def test_sentinel_prevents_double_lookup(self, async_db: AsyncSession):
        row = _make_row("es", "tiempo", {"etymology_attempted": True})
        async_db.add(row)
        await async_db.commit()

        await apply_etymology(async_db, [row.id])

        await async_db.refresh(row)
        # Already attempted — no etymology written (row had no entry before)
        assert (row.lesson_data or {}).get("etymology") is None

    @pytest.mark.asyncio
    async def test_non_vocabulary_type_skipped(self, async_db: AsyncSession):
        row = CanonicalObjectRow()
        row.id = canonical_object_id("es", "conjugation", "hablar")
        row.language = "es"
        row.type = "conjugation"
        row.canonical_form = "hablar"
        row.display_label = "hablar"
        row.lesson_data = {"lemma": "hablar"}
        async_db.add(row)
        await async_db.commit()

        await apply_etymology(async_db, [row.id])

        await async_db.refresh(row)
        assert (row.lesson_data or {}).get("etymology") is None

    @pytest.mark.asyncio
    async def test_empty_object_ids_no_op(self, async_db: AsyncSession):
        # Should not raise or query DB
        await apply_etymology(async_db, [])

    @pytest.mark.asyncio
    async def test_custom_store_used(self, async_db: AsyncSession):
        custom_store = EtymologyStore([
            EtymologyEntry(language="xx", lemma="foo", origin_summary="Custom origin.")
        ])
        row = _make_row("xx", "foo")
        async_db.add(row)
        await async_db.commit()

        await apply_etymology(async_db, [row.id], store=custom_store)

        await async_db.refresh(row)
        etym = (row.lesson_data or {}).get("etymology")
        assert etym is not None
        assert etym["origin_summary"] == "Custom origin."

    @pytest.mark.asyncio
    async def test_rtl_script_stored_and_retrieved(self, async_db: AsyncSession):
        row = _make_row("ar", "قلم")
        async_db.add(row)
        await async_db.commit()

        await apply_etymology(async_db, [row.id])

        await async_db.refresh(row)
        etym = (row.lesson_data or {}).get("etymology")
        assert etym is not None
        assert isinstance(etym["origin_summary"], str)
        assert len(etym["origin_summary"]) > 0

    @pytest.mark.asyncio
    async def test_cjk_script_stored_and_retrieved(self, async_db: AsyncSession):
        row = _make_row("zh", "茶")
        async_db.add(row)
        await async_db.commit()

        await apply_etymology(async_db, [row.id])

        await async_db.refresh(row)
        etym = (row.lesson_data or {}).get("etymology")
        assert etym is not None
        assert isinstance(etym["origin_summary"], str)
