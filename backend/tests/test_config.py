from __future__ import annotations

from backend.core.config import Settings


def _settings(**kwargs) -> Settings:
    return Settings(database_url="sqlite+aiosqlite:///:memory:", **kwargs)


def test_enabled_languages_accepts_single_comma_separated_env_value(monkeypatch):
    """Smoke CI writes ENABLED_LANGUAGES=es, so settings must parse it."""
    monkeypatch.setenv("ENABLED_LANGUAGES", "es")

    settings = _settings(_env_file=None)

    assert settings.enabled_languages == ["es"]


def test_enabled_languages_accepts_multiple_comma_separated_values():
    settings = _settings(enabled_languages="es, fr, de")

    assert settings.enabled_languages == ["es", "fr", "de"]


def test_list_settings_still_accept_json_arrays():
    settings = _settings(
        enabled_languages='["es", "fr"]',
        cors_origins='["https://app.example.com"]',
    )

    assert settings.enabled_languages == ["es", "fr"]
    assert settings.cors_origins == ["https://app.example.com"]
