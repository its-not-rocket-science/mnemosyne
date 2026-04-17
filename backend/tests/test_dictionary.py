"""Tests for the Wiktionary dictionary integration.

Covers:
- strip_html() — pure function
- _extract_first_definition() — pure function
- fetch_definition() — async, HTTP mocked with respx
- enrich_objects() — async, DB-level tests with SQLite fixture
"""
from __future__ import annotations

import pytest
import pytest_asyncio
import respx
import httpx
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.dictionary.wiktionary import (
    BCP47_TO_WIKTIONARY,
    _extract_first_definition,
    fetch_definition,
    strip_html,
)
from backend.dictionary.enrichment import (
    ENRICHMENT_TYPES,
    enrich_objects,
)
from backend.models import Base, CanonicalObjectRow
from backend.parsing.canonical import canonical_object_id


# ── strip_html ────────────────────────────────────────────────────────────────

class TestStripHtml:
    def test_removes_bold(self):
        assert strip_html("<b>cat</b>") == "cat"

    def test_removes_link(self):
        assert strip_html('<a href="/wiki/Cat">Cat</a>') == "Cat"

    def test_removes_span(self):
        assert strip_html('<span class="usex">Example sentence.</span>') == "Example sentence."

    def test_collapses_whitespace(self):
        assert strip_html("word  with   spaces") == "word with spaces"

    def test_combined(self):
        result = strip_html('A <b>domestic</b> animal (<i>Felis catus</i>).')
        assert result == "A domestic animal (Felis catus)."

    def test_empty_string(self):
        assert strip_html("") == ""

    def test_no_tags(self):
        assert strip_html("plain text") == "plain text"


# ── _extract_first_definition ─────────────────────────────────────────────────

class TestExtractFirstDefinition:
    _RESPONSE = {
        "es": [
            {
                "partOfSpeech": "Noun",
                "definitions": [
                    {"definition": "A <b>cat</b>, especially a domestic one."},
                    {"definition": "Second definition."},
                ],
            },
            {
                "partOfSpeech": "Verb",
                "definitions": [{"definition": "To act like a cat."}],
            },
        ],
        "en": [
            {
                "partOfSpeech": "Noun",
                "definitions": [{"definition": "English meaning."}],
            }
        ],
    }

    def test_extracts_first_definition_for_target_lang(self):
        result = _extract_first_definition(self._RESPONSE, "es")
        assert result == "A cat, especially a domestic one."

    def test_uses_correct_language_section(self):
        result = _extract_first_definition(self._RESPONSE, "en")
        assert result == "English meaning."

    def test_missing_language_returns_none(self):
        result = _extract_first_definition(self._RESPONSE, "fr")
        assert result is None

    def test_empty_definitions_skipped(self):
        data = {"es": [{"partOfSpeech": "Noun", "definitions": []}]}
        assert _extract_first_definition(data, "es") is None

    def test_empty_definition_string_skipped(self):
        data = {
            "es": [
                {"partOfSpeech": "Noun", "definitions": [{"definition": "   "}]},
                {"partOfSpeech": "Verb", "definitions": [{"definition": "To run."}]},
            ]
        }
        result = _extract_first_definition(data, "es")
        assert result == "To run."

    def test_no_language_entry(self):
        assert _extract_first_definition({}, "es") is None


# ── fetch_definition ──────────────────────────────────────────────────────────

MOCK_BASE = "https://mock-wiktionary.test"


@pytest.mark.asyncio
@respx.mock
async def test_fetch_definition_returns_gloss():
    respx.get(f"{MOCK_BASE}/page/definition/gato").mock(
        return_value=httpx.Response(
            200,
            json={
                "es": [
                    {
                        "partOfSpeech": "Noun",
                        "definitions": [
                            {"definition": "cat (<i>Felis catus</i>)"}
                        ],
                    }
                ]
            },
        )
    )
    result = await fetch_definition("gato", "es", base_url=MOCK_BASE)
    assert result == "cat (Felis catus)"


@pytest.mark.asyncio
@respx.mock
async def test_fetch_definition_404_returns_none():
    respx.get(f"{MOCK_BASE}/page/definition/xyzzy").mock(
        return_value=httpx.Response(404, json={"detail": "Not found"})
    )
    result = await fetch_definition("xyzzy", "es", base_url=MOCK_BASE)
    assert result is None


@pytest.mark.asyncio
async def test_fetch_definition_unknown_language():
    # No HTTP request should be made for an unknown language code.
    result = await fetch_definition("test", "xx", base_url=MOCK_BASE)
    assert result is None


@pytest.mark.asyncio
@respx.mock
async def test_fetch_definition_missing_language_section_returns_none():
    respx.get(f"{MOCK_BASE}/page/definition/chat").mock(
        return_value=httpx.Response(
            200,
            json={"fr": [{"partOfSpeech": "Noun", "definitions": [{"definition": "cat"}]}]},
        )
    )
    # Look up "es" section but only "fr" is present
    result = await fetch_definition("chat", "es", base_url=MOCK_BASE)
    assert result is None


@pytest.mark.asyncio
@respx.mock
async def test_fetch_definition_non_ascii_lemma():
    """Non-ASCII lemmas are URL-encoded correctly."""
    respx.get(f"{MOCK_BASE}/page/definition/%D0%BA%D0%BE%D1%88%D0%BA%D0%B0").mock(
        return_value=httpx.Response(
            200,
            json={
                "ru": [
                    {
                        "partOfSpeech": "Noun",
                        "definitions": [{"definition": "a cat"}],
                    }
                ]
            },
        )
    )
    result = await fetch_definition("кошка", "ru", base_url=MOCK_BASE)
    assert result == "a cat"


@pytest.mark.asyncio
@respx.mock
async def test_fetch_definition_raises_on_server_error():
    respx.get(f"{MOCK_BASE}/page/definition/fail").mock(
        return_value=httpx.Response(500, text="Internal Server Error")
    )
    with pytest.raises(httpx.HTTPStatusError):
        await fetch_definition("fail", "es", base_url=MOCK_BASE)


# ── enrich_objects (DB integration) ──────────────────────────────────────────

@pytest_asyncio.fixture
async def db_engine(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/test.db")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine):
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session


def _make_vocab_row(language: str = "es", canonical_form: str = "gato") -> CanonicalObjectRow:
    obj_id = canonical_object_id(language, "vocabulary", canonical_form)
    return CanonicalObjectRow(
        id=obj_id,
        language=language,
        type="vocabulary",
        canonical_form=canonical_form,
        display_label=canonical_form,
        lesson_data={},
    )


@pytest.mark.asyncio
async def test_enrich_skips_empty_list(db_session):
    await enrich_objects(db_session, [])  # should not raise


@pytest.mark.asyncio
async def test_enrich_skips_non_vocabulary_types(db_session):
    obj_id = canonical_object_id("es", "conjugation", "corre")
    row = CanonicalObjectRow(
        id=obj_id,
        language="es",
        type="conjugation",
        canonical_form="corre",
        display_label="corre",
        lesson_data={},
    )
    db_session.add(row)
    await db_session.commit()

    # Patch fetch_definition to assert it is never called
    import backend.dictionary.enrichment as mod
    called = []
    orig = mod.fetch_definition
    async def _spy(*a, **kw):
        called.append(a)
        return await orig(*a, **kw)
    mod.fetch_definition = _spy

    await enrich_objects(db_session, [obj_id])
    mod.fetch_definition = orig

    assert not called, "fetch_definition should not be called for non-vocabulary objects"


@pytest.mark.asyncio
async def test_enrich_skips_already_enriched(db_session):
    row = _make_vocab_row()
    row.lesson_data = {"gloss": "existing gloss"}
    db_session.add(row)
    await db_session.commit()

    import backend.dictionary.enrichment as mod
    called = []
    orig = mod.fetch_definition
    async def _spy(*a, **kw):
        called.append(a)
        return await orig(*a, **kw)
    mod.fetch_definition = _spy

    await enrich_objects(db_session, [row.id])
    mod.fetch_definition = orig

    assert not called


@pytest.mark.asyncio
async def test_enrich_skips_previously_attempted(db_session):
    row = _make_vocab_row()
    row.lesson_data = {"gloss_attempted": True}
    db_session.add(row)
    await db_session.commit()

    import backend.dictionary.enrichment as mod
    called = []
    orig = mod.fetch_definition
    async def _spy(*a, **kw):
        called.append(a)
        return await orig(*a, **kw)
    mod.fetch_definition = _spy

    await enrich_objects(db_session, [row.id])
    mod.fetch_definition = orig

    assert not called


@pytest.mark.asyncio
async def test_enrich_stores_gloss_when_found(db_session):
    row = _make_vocab_row()
    db_session.add(row)
    await db_session.commit()

    import backend.dictionary.enrichment as mod
    orig = mod.fetch_definition
    mod.fetch_definition = lambda lemma, lang, **kw: _async_return("a domestic cat")

    await enrich_objects(db_session, [row.id])
    mod.fetch_definition = orig

    await db_session.refresh(row)
    assert row.lesson_data["gloss"] == "a domestic cat"
    assert row.lesson_data["gloss_attempted"] is True


@pytest.mark.asyncio
async def test_enrich_marks_attempted_when_not_found(db_session):
    row = _make_vocab_row()
    db_session.add(row)
    await db_session.commit()

    import backend.dictionary.enrichment as mod
    orig = mod.fetch_definition
    mod.fetch_definition = lambda lemma, lang, **kw: _async_return(None)

    await enrich_objects(db_session, [row.id])
    mod.fetch_definition = orig

    await db_session.refresh(row)
    assert row.lesson_data.get("gloss") is None
    assert row.lesson_data["gloss_attempted"] is True


@pytest.mark.asyncio
async def test_enrich_does_not_mark_attempted_on_network_error(db_session):
    row = _make_vocab_row()
    db_session.add(row)
    await db_session.commit()

    import backend.dictionary.enrichment as mod
    orig = mod.fetch_definition

    async def _fail(lemma, lang, **kw):
        raise httpx.RequestError("timeout")

    mod.fetch_definition = _fail
    await enrich_objects(db_session, [row.id])
    mod.fetch_definition = orig

    await db_session.refresh(row)
    # On network error, leave untagged so retry is possible
    assert "gloss_attempted" not in row.lesson_data


# ── bcp47 coverage ────────────────────────────────────────────────────────────

def test_all_mnemosyne_languages_mapped():
    """All languages with full NLP plugins should have a Wiktionary mapping."""
    # At minimum, these languages must have Wiktionary coverage.
    required = {"es", "fr", "de", "ru", "ja", "zh", "ar", "he", "la"}
    missing = required - BCP47_TO_WIKTIONARY.keys()
    assert not missing, f"Languages missing from BCP47_TO_WIKTIONARY: {missing}"


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _async_return(value):
    return value
