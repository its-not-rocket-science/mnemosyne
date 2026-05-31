from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi import HTTPException

from backend.api.routes.sources import _distributed_due_at, _require_source_document


class _FakeMissingDb:
    async def scalar(self, _stmt):
        return None


def test_distributed_due_at_immediate_when_spread_days_zero():
    now = datetime(2026, 5, 30, 12, 0, tzinfo=UTC)

    assert _distributed_due_at(now, 0, limit=100, spread_days=0) == now
    assert _distributed_due_at(now, 50, limit=100, spread_days=0) == now


def test_distributed_due_at_spreads_within_window():
    now = datetime(2026, 5, 30, 12, 0, tzinfo=UTC)

    first = _distributed_due_at(now, 0, limit=100, spread_days=4)
    middle = _distributed_due_at(now, 50, limit=100, spread_days=4)
    last = _distributed_due_at(now, 99, limit=100, spread_days=4)

    assert first == now
    assert 0 <= (middle - now).days <= 4
    assert 0 <= (last - now).days <= 4
    assert first <= middle <= last


@pytest.mark.asyncio
async def test_require_source_document_raises_404_for_missing_doc():
    with pytest.raises(HTTPException) as exc:
        await _require_source_document(_FakeMissingDb(), "missing-doc-id")  # type: ignore[arg-type]

    assert exc.value.status_code == 404
    assert exc.value.detail == "Document not found"
