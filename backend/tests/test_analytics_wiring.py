"""Verify that route handlers call maybe_record_event at the right call sites.

Strategy: patch maybe_record_event in each route module and assert it is
called (or not) with the expected arguments.  DB interaction is mocked so
tests stay fast and do not need a real database.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from backend.api.dependencies import get_current_user, get_db_session, get_plugin_registry
from backend.main import app


# ── shared helpers ────────────────────────────────────────────────────────────

def _mock_db() -> AsyncMock:
    """Return a minimal AsyncSession mock that satisfies route code."""
    db = AsyncMock()
    db.get = AsyncMock(return_value=None)
    db.execute = AsyncMock(return_value=MagicMock(scalars=MagicMock(return_value=[]), scalar_one_or_none=MagicMock(return_value=None), all=MagicMock(return_value=[])))
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    return db


def _mock_registry(language: str = "en") -> MagicMock:
    registry = MagicMock()
    plugin = MagicMock()
    plugin.lesson_store = {}
    plugin.capabilities = MagicMock()
    plugin.capabilities.tokenization_mode = "whitespace"
    registry.get = MagicMock(return_value=plugin)
    return registry


def _override_auth(user_id: str = "test-user"):
    app.dependency_overrides[get_current_user] = lambda: user_id


def _clear_overrides():
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_db_session, None)
    app.dependency_overrides.pop(get_plugin_registry, None)


# ── ingest: maybe_record_event called on success, skipped on persist failure ──

class TestIngestAnalyticsWiring:
    @pytest.mark.asyncio
    async def test_event_recorded_on_successful_persist(self):
        db = _mock_db()
        registry = _mock_registry()
        _override_auth()
        app.dependency_overrides[get_db_session] = lambda: db
        app.dependency_overrides[get_plugin_registry] = lambda: registry

        with (
            patch("backend.api.routes.ingest.run_pipeline", new_callable=AsyncMock) as mock_pipeline,
            patch("backend.api.routes.ingest.persist_ingest", new_callable=AsyncMock) as mock_persist,
            patch("backend.api.routes.ingest.maybe_record_event", new_callable=AsyncMock) as mock_event,
        ):
            from backend.schemas.parse import SentenceResult
            mock_result = MagicMock()
            mock_result.cache_hit = False
            mock_result.sentences = [MagicMock(spec=SentenceResult, text="Test.", learnable_objects=[])]
            mock_result.candidate_results = []
            mock_result.uuid_to_candidate = {}
            mock_pipeline.return_value = mock_result

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.post(
                    "/ingest",
                    json={"text": "Test sentence here.", "language": "en", "content_type": "pasted_text"},
                    headers={"Authorization": "Bearer test"},
                )

            mock_event.assert_awaited_once()
            call_kwargs = mock_event.call_args
            assert call_kwargs.args[2] == "text_ingested"

        _clear_overrides()

    @pytest.mark.asyncio
    async def test_event_not_recorded_when_persist_raises(self):
        db = _mock_db()
        registry = _mock_registry()
        _override_auth()
        app.dependency_overrides[get_db_session] = lambda: db
        app.dependency_overrides[get_plugin_registry] = lambda: registry

        with (
            patch("backend.api.routes.ingest.run_pipeline", new_callable=AsyncMock) as mock_pipeline,
            patch("backend.api.routes.ingest.persist_ingest", new_callable=AsyncMock, side_effect=Exception("DB error")),
            patch("backend.api.routes.ingest.maybe_record_event", new_callable=AsyncMock) as mock_event,
        ):
            from backend.schemas.parse import SentenceResult
            mock_result = MagicMock()
            mock_result.cache_hit = False
            mock_result.sentences = [MagicMock(spec=SentenceResult, text="Test.", learnable_objects=[])]
            mock_result.candidate_results = []
            mock_result.uuid_to_candidate = {}
            mock_pipeline.return_value = mock_result

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                await client.post(
                    "/ingest",
                    json={"text": "Test sentence here.", "language": "en", "content_type": "pasted_text"},
                    headers={"Authorization": "Bearer test"},
                )

            mock_event.assert_not_awaited()

        _clear_overrides()


# ── review: maybe_record_event called after commit ────────────────────────────

class TestReviewAnalyticsWiring:
    @pytest.mark.asyncio
    async def test_event_recorded_per_review(self):
        db = _mock_db()
        from backend.models import CanonicalObjectRow, UserFsrsParamsRow
        canonical = MagicMock(spec=CanonicalObjectRow)
        canonical.type = "vocabulary"
        canonical.language = "es"
        canonical.display_label = "hablar"
        canonical.canonical_form = "hablar"

        async def _mock_get(model, pk):
            if model is CanonicalObjectRow:
                return canonical
            if model is UserFsrsParamsRow:
                return None
            return None

        db.get = AsyncMock(side_effect=_mock_get)

        _override_auth()
        app.dependency_overrides[get_db_session] = lambda: db

        with patch("backend.api.routes.review.maybe_record_event", new_callable=AsyncMock) as mock_event:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.post(
                    "/review",
                    json={
                        "object_id": "obj-123",
                        "quality": 4,
                        "review_state": None,
                        "wrong_answer": None,
                    },
                    headers={"Authorization": "Bearer test"},
                )

            mock_event.assert_awaited_once()
            args = mock_event.call_args
            assert args.args[2] == "review_session"
            assert args.kwargs.get("language") == "es"

        _clear_overrides()


# ── recommend: maybe_record_event called with count=len(result_sentences) ─────

class TestRecommendAnalyticsWiring:
    @pytest.mark.asyncio
    async def test_event_recorded_with_sentence_count(self):
        db = _mock_db()

        # Empty mastery → no sentences returned, but event still fires
        _override_auth()
        app.dependency_overrides[get_db_session] = lambda: db

        with patch("backend.api.routes.recommend.maybe_record_event", new_callable=AsyncMock) as mock_event:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.get(
                    "/recommend-text?language=es",
                    headers={"Authorization": "Bearer test"},
                )

            mock_event.assert_awaited_once()
            args = mock_event.call_args
            assert args.args[2] == "recommend_served"
            assert args.kwargs.get("language") == "es"

        _clear_overrides()
