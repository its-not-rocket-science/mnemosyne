"""Shared pytest configuration for the Mnemosyne test suite."""
from __future__ import annotations

import json
from pathlib import Path

import pytest


# ── Per-language gold coverage summary ───────────────────────────────────────

def pytest_terminal_summary(terminalreporter, exitstatus, config):  # noqa: ANN001
    """Print a per-language gold-test coverage summary after the test run.

    Reports how many gold cases passed and failed for each language that
    has a fixture file in backend/tests/fixtures/nuance_gold/.  Skipped
    cases (plugin unavailable) are shown separately so uneven language
    quality is visible rather than hidden.
    """
    gold_dir = Path(__file__).parent / "fixtures" / "nuance_gold"
    if not gold_dir.exists():
        return

    lang_codes = sorted(
        p.stem for p in gold_dir.glob("*.json")
    )
    if not lang_codes:
        return

    passed  = {r.nodeid: r for r in terminalreporter.stats.get("passed",  [])}
    failed  = {r.nodeid: r for r in terminalreporter.stats.get("failed",  [])}
    skipped = {r.nodeid: r for r in terminalreporter.stats.get("skipped", [])}

    rows: list[tuple[str, int, int, int]] = []
    for lang in lang_codes:
        p_count = sum(1 for nid in passed  if f"[{lang}_" in nid or f"[{lang}-" in nid)
        f_count = sum(1 for nid in failed  if f"[{lang}_" in nid or f"[{lang}-" in nid)
        s_count = sum(1 for nid in skipped if f"[{lang}_" in nid or f"[{lang}-" in nid)
        if p_count + f_count + s_count > 0:
            rows.append((lang, p_count, f_count, s_count))

    if not rows:
        return

    terminalreporter.write_sep("-", "Gold test coverage by language", yellow=True)
    header = f"{'Lang':<6}  {'Pass':>5}  {'Fail':>5}  {'Skip':>5}"
    terminalreporter.write_line(header)
    for lang, p, f, s in rows:
        status = "✓" if f == 0 and p > 0 else ("✗" if f > 0 else "–")
        terminalreporter.write_line(f"{lang:<6}  {p:>5}  {f:>5}  {s:>5}  {status}")


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
