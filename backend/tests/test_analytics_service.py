"""Unit tests for backend/services/analytics.py.

Tests run without a DB (mocked session) to stay fast.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.analytics import (
    _sanitize_metadata,
    _VALID_EVENT_TYPES,
    delete_user_events,
    maybe_record_event,
    record_event,
)


class TestValidEventTypes:
    def test_all_expected_types_present(self):
        assert "review_session" in _VALID_EVENT_TYPES
        assert "text_ingested" in _VALID_EVENT_TYPES
        assert "recommend_served" in _VALID_EVENT_TYPES
        assert "practice_drill" in _VALID_EVENT_TYPES


class TestSanitizeMetadata:
    def test_removes_banned_keys(self):
        meta = {"text": "hello", "language": "es", "count": 5}
        _sanitize_metadata(meta)
        assert "text" not in meta
        assert meta["language"] == "es"
        assert meta["count"] == 5

    def test_removes_all_banned_keys(self):
        meta = {
            "text": "x",
            "sentence": "y",
            "canonical_form": "z",
            "surface_form": "a",
            "answer": "b",
            "hint": "c",
            "language": "fr",
        }
        _sanitize_metadata(meta)
        for banned in ("text", "sentence", "canonical_form", "surface_form", "answer", "hint"):
            assert banned not in meta
        assert meta["language"] == "fr"

    def test_empty_meta_unchanged(self):
        meta: dict = {}
        _sanitize_metadata(meta)
        assert meta == {}


class TestRecordEvent:
    @pytest.mark.asyncio
    async def test_valid_event_written(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock()
        await record_event(db, "user-1", "review_session", language="es", count=5)
        db.add.assert_called_once()
        db.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_unknown_event_type_skipped(self):
        db = AsyncMock()
        db.add = MagicMock()
        await record_event(db, "user-1", "unknown_type")
        db.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_count_clamped_to_minimum_1(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock()
        await record_event(db, "user-1", "review_session", count=-5)
        call_args = db.add.call_args[0][0]
        assert call_args.count >= 1

    @pytest.mark.asyncio
    async def test_db_error_is_non_fatal(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock(side_effect=Exception("DB down"))
        # Should not raise
        await record_event(db, "user-1", "review_session")


class TestMaybeRecordEvent:
    @pytest.mark.asyncio
    async def test_opted_out_user_skips_event(self):
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = True  # opted out
        db.execute = AsyncMock(return_value=mock_result)
        db.add = MagicMock()

        await maybe_record_event(db, "user-1", "review_session")
        db.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_opted_in_user_records_event(self):
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = False  # opted in
        db.execute = AsyncMock(return_value=mock_result)
        db.add = MagicMock()
        db.flush = AsyncMock()

        await maybe_record_event(db, "user-1", "review_session", language="es")
        db.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_db_error_on_opt_out_check_skips_silently(self):
        db = AsyncMock()
        db.execute = AsyncMock(side_effect=Exception("DB down"))
        db.add = MagicMock()

        await maybe_record_event(db, "user-1", "review_session")
        db.add.assert_not_called()


class TestDeleteUserEvents:
    @pytest.mark.asyncio
    async def test_returns_rowcount(self):
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.rowcount = 7
        db.execute = AsyncMock(return_value=mock_result)
        db.flush = AsyncMock()

        count = await delete_user_events(db, "user-1")
        assert count == 7
