"""B8 — Sentry error monitoring tests.

Strategy
────────
We don't need a real Sentry DSN — we patch ``sentry_sdk.init`` and
``sentry_sdk.is_initialized`` to verify that ``_init_sentry`` behaves
correctly under different config combinations without making any network calls.
"""
from __future__ import annotations

from unittest.mock import call, patch, MagicMock

import pytest

from backend.core.config import Settings
from backend.main import _init_sentry


def _settings(**kwargs) -> Settings:
    return Settings(database_url="sqlite+aiosqlite:///:memory:", **kwargs)


# ── No-op when DSN is absent ──────────────────────────────────────────────────


def test_sentry_not_initialised_without_dsn():
    """_init_sentry must not call sentry_sdk.init when sentry_dsn is unset."""
    s = _settings(sentry_dsn=None)
    with patch("backend.main.sentry_sdk.init") as mock_init:
        _init_sentry(s)
    mock_init.assert_not_called()


def test_sentry_not_initialised_with_empty_dsn():
    """An empty-string DSN should be treated the same as None."""
    s = _settings(sentry_dsn="")
    with patch("backend.main.sentry_sdk.init") as mock_init:
        _init_sentry(s)
    mock_init.assert_not_called()


# ── Initialised when DSN is present ──────────────────────────────────────────


def test_sentry_initialised_with_dsn():
    """_init_sentry calls sentry_sdk.init exactly once when a DSN is set."""
    s = _settings(sentry_dsn="https://key@sentry.io/123")
    with patch("backend.main.sentry_sdk.init") as mock_init:
        _init_sentry(s)
    mock_init.assert_called_once()
    kwargs = mock_init.call_args.kwargs
    assert kwargs["dsn"] == "https://key@sentry.io/123"


def test_sentry_pii_disabled_by_default():
    """send_default_pii must be False to protect user privacy."""
    s = _settings(sentry_dsn="https://key@sentry.io/123")
    with patch("backend.main.sentry_sdk.init") as mock_init:
        _init_sentry(s)
    kwargs = mock_init.call_args.kwargs
    assert kwargs.get("send_default_pii") is False


# ── Environment tag logic ─────────────────────────────────────────────────────


def test_sentry_environment_defaults_to_production_when_not_debug():
    """When debug=False and no explicit env, environment should be 'production'."""
    s = _settings(
        sentry_dsn="https://key@sentry.io/123",
        debug=False,
        cors_origins=["https://app.example.com"],
        jwt_secret="strong-secret-for-test-only-32chars!",
        sentry_environment=None,
    )
    with patch("backend.main.sentry_sdk.init") as mock_init:
        _init_sentry(s)
    kwargs = mock_init.call_args.kwargs
    assert kwargs["environment"] == "production"


def test_sentry_environment_defaults_to_development_when_debug():
    """When debug=True and no explicit env, environment should be 'development'."""
    s = _settings(
        sentry_dsn="https://key@sentry.io/123",
        debug=True,
        sentry_environment=None,
    )
    with patch("backend.main.sentry_sdk.init") as mock_init:
        _init_sentry(s)
    kwargs = mock_init.call_args.kwargs
    assert kwargs["environment"] == "development"


def test_sentry_environment_explicit_override():
    """An explicit sentry_environment value takes precedence over the debug flag."""
    s = _settings(
        sentry_dsn="https://key@sentry.io/123",
        debug=True,
        sentry_environment="staging",
    )
    with patch("backend.main.sentry_sdk.init") as mock_init:
        _init_sentry(s)
    kwargs = mock_init.call_args.kwargs
    assert kwargs["environment"] == "staging"


# ── Integrations ──────────────────────────────────────────────────────────────


def test_sentry_includes_fastapi_and_starlette_integrations():
    """Both FastApiIntegration and StarletteIntegration must be registered."""
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.starlette import StarletteIntegration

    s = _settings(sentry_dsn="https://key@sentry.io/123")
    with patch("backend.main.sentry_sdk.init") as mock_init:
        _init_sentry(s)

    integrations = mock_init.call_args.kwargs.get("integrations", [])
    types = {type(i) for i in integrations}
    assert FastApiIntegration in types
    assert StarletteIntegration in types
