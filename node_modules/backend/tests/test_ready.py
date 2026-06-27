"""Tests for GET /ready — readiness probe with plugin degradation reporting.

All tests use the synchronous TestClient.  DB and Redis checks are expected to
fail (no live services in CI) so the overall status is "degraded", but the
plugins field is what we exercise here.
"""
from __future__ import annotations

import unittest.mock as mock

from fastapi.testclient import TestClient

from backend.api.dependencies import get_plugin_registry
from backend.main import app
from backend.parsing.plugin_loader import PluginRegistry


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_registry(failed: dict[str, str] | None = None) -> PluginRegistry:
    r = PluginRegistry()
    if failed:
        r._failed.update(failed)
    return r


# ── tests ─────────────────────────────────────────────────────────────────────


def test_ready_plugins_ok_when_no_failures():
    """When all plugins loaded, plugins field is 'ok'."""
    registry = _make_registry()
    app.dependency_overrides[get_plugin_registry] = lambda: registry
    try:
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/ready")
        data = resp.json()
        assert data["plugins"] == "ok"
    finally:
        app.dependency_overrides.pop(get_plugin_registry, None)


def test_ready_plugins_degraded_when_plugin_failed():
    """When a plugin failed to load, plugins field lists the failing module."""
    registry = _make_registry({"backend.plugins.broken": "OSError: model not found"})
    app.dependency_overrides[get_plugin_registry] = lambda: registry
    try:
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/ready")
        data = resp.json()
        assert isinstance(data["plugins"], dict)
        assert "backend.plugins.broken" in data["plugins"]["degraded"]
    finally:
        app.dependency_overrides.pop(get_plugin_registry, None)


def test_ready_status_degraded_when_plugin_failed():
    """A plugin failure makes the overall status 'degraded' (503)."""
    registry = _make_registry({"backend.plugins.broken": "OSError: model not found"})
    app.dependency_overrides[get_plugin_registry] = lambda: registry
    try:
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/ready")
        assert resp.status_code == 503
        assert resp.json()["status"] == "degraded"
    finally:
        app.dependency_overrides.pop(get_plugin_registry, None)


def test_ready_multiple_failed_plugins_all_listed():
    """All failing module names are reported when multiple plugins fail."""
    registry = _make_registry({
        "backend.plugins.alpha": "ImportError: missing dep",
        "backend.plugins.beta":  "OSError: model not found",
    })
    app.dependency_overrides[get_plugin_registry] = lambda: registry
    try:
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/ready")
        degraded = set(resp.json()["plugins"]["degraded"])
        assert "backend.plugins.alpha" in degraded
        assert "backend.plugins.beta" in degraded
    finally:
        app.dependency_overrides.pop(get_plugin_registry, None)


def test_ready_has_db_and_redis_fields():
    """Response always includes db, redis, and plugins fields."""
    registry = _make_registry()
    app.dependency_overrides[get_plugin_registry] = lambda: registry
    try:
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/ready")
        data = resp.json()
        assert "db" in data
        assert "redis" in data
        assert "plugins" in data
        assert "status" in data
    finally:
        app.dependency_overrides.pop(get_plugin_registry, None)


def test_failed_plugins_recorded_on_load_error():
    """PluginRegistry.failed_plugins() returns failures from load_plugins()."""
    from backend.parsing.plugin_loader import PluginRegistry

    registry = PluginRegistry()

    # Simulate what load_plugins() does on exception
    try:
        raise OSError("model file not found")
    except Exception as exc:
        registry._failed["backend.plugins.mock_lang"] = f"{type(exc).__name__}: {exc}"

    failures = registry.failed_plugins()
    assert "backend.plugins.mock_lang" in failures
    assert "OSError" in failures["backend.plugins.mock_lang"]


def test_failed_plugins_empty_when_all_ok():
    """PluginRegistry.failed_plugins() returns {} when no failures."""
    registry = PluginRegistry()
    assert registry.failed_plugins() == {}
