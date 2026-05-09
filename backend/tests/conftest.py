"""Shared pytest configuration for the Mnemosyne test suite."""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def disable_redis_cache(monkeypatch):
    """Disable the Redis parse cache for all tests.

    When Redis is running locally and has cached parse results from a previous
    run, the /parse route returns the cached response and skips scheduling the
    background persistence task.  This causes any test that calls /parse and
    then inspects the database to fail non-deterministically.

    Patching get_json to always miss and set_json to no-op ensures the full
    NLP + background-persist path is exercised every time.
    """
    async def _no_cache(key: str):  # noqa: ANN001
        return None

    async def _noop_set(key: str, value, ttl_seconds: int = 3600) -> None:  # noqa: ANN001
        pass

    # Both routes delegate to pipeline.py, which imports these names directly.
    monkeypatch.setattr("backend.parsing.pipeline.get_json", _no_cache)
    monkeypatch.setattr("backend.parsing.pipeline.set_json", _noop_set)


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """Reset in-memory rate-limit counters before every test.

    Without a reset, the 20/minute parse limit is exhausted after ~20 tests
    that call /parse, causing the remainder to fail with 429.
    """
    from backend.core.limiter import limiter
    limiter._limiter.storage.reset()
