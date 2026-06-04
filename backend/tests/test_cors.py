"""CORS lockdown tests — B5.

Verifies that:
  - Wildcard CORS is rejected at Settings construction time when DEBUG=False.
  - Specific origins are accepted in production mode.
  - Wildcard is still accepted in debug mode (local dev convenience).

The Starlette CORSMiddleware correctly reflects whichever allow-list is
configured; its behaviour is tested upstream.  Our responsibility is ensuring
the validator prevents a wildcard allow-list from ever reaching a production
deployment.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.core.config import Settings


def test_wildcard_cors_rejected_in_production():
    """Settings must raise if cors_origins=['*'] and debug=False."""
    with pytest.raises(ValidationError, match="Wildcard CORS"):
        Settings(
            database_url="sqlite+aiosqlite:///:memory:",
            debug=False,
            cors_origins=["*"],
        )


def test_wildcard_cors_allowed_in_debug_mode():
    """Default wildcard is fine for local development (debug=True)."""
    s = Settings(
        database_url="sqlite+aiosqlite:///:memory:",
        debug=True,
        cors_origins=["*"],
    )
    assert "*" in s.cors_origins


def test_specific_origins_accepted_in_production():
    """Explicit origin list must be accepted when debug=False."""
    s = Settings(
        database_url="sqlite+aiosqlite:///:memory:",
        debug=False,
        cors_origins=["https://app.example.com", "https://staging.example.com"],
        jwt_secret="strong-secret-for-test-only-32chars!",
    )
    assert "https://app.example.com" in s.cors_origins


def test_multiple_wildcard_entries_still_rejected():
    """Having '*' anywhere in the list triggers the guard."""
    with pytest.raises(ValidationError, match="Wildcard CORS"):
        Settings(
            database_url="sqlite+aiosqlite:///:memory:",
            debug=False,
            cors_origins=["https://app.example.com", "*"],
        )


def test_list_settings_accept_comma_separated_env_values(monkeypatch):
    """List settings should accept the documented comma-separated env syntax."""
    monkeypatch.setenv("ENABLED_LANGUAGES", "es, fr")
    monkeypatch.setenv("CORS_ORIGINS", "https://app.example.com, https://staging.example.com")

    s = Settings(database_url="sqlite+aiosqlite:///:memory:", debug=False)

    assert s.enabled_languages == ["es", "fr"]
    assert s.cors_origins == [
        "https://app.example.com",
        "https://staging.example.com",
    ]


def test_single_enabled_language_env_value_is_a_one_item_list(monkeypatch):
    """The smoke workflow uses ENABLED_LANGUAGES=es to limit startup work."""
    monkeypatch.setenv("ENABLED_LANGUAGES", "es")

    s = Settings(database_url="sqlite+aiosqlite:///:memory:")

    assert s.enabled_languages == ["es"]
