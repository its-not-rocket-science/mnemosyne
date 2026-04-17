from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Mnemosyne"
    debug: bool = True
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/mnemosyne"
    )
    redis_url: str = Field(default="redis://localhost:6379/0")
    plugin_package: str = "backend.plugins"
    # Explicit allow-list of language codes to activate.  None (default) means
    # all plugins with a create_plugin() factory are loaded.  Set to e.g.
    # ["es", "fr"] in .env as ENABLED_LANGUAGES=es,fr to limit the active set.
    enabled_languages: list[str] | None = None
    # Comma-separated list of allowed CORS origins.  The default wildcard is
    # intentionally permissive for local development only.  In production
    # (DEBUG=False) a wildcard origin is rejected at startup — set
    # CORS_ORIGINS=https://yourapp.example.com in .env before deploying.
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])
    # Maximum number of characters accepted by /parse and /ingest before the
    # NLP pipeline is invoked.  Protects against event-loop blocking on large
    # pastes.  Set MAX_PARSE_CHARS in .env to override.
    max_parse_chars: int = 10_000
    # JWT authentication settings.
    # jwt_secret MUST be overridden in production via the JWT_SECRET env var.
    # The default is intentionally weak so it fails loudly if deployed as-is.
    jwt_secret: str = Field(
        default="CHANGE_ME_IN_PRODUCTION",
        description="HS256 signing secret for JWT tokens.",
    )
    jwt_algorithm: str = "HS256"
    # Token lifetime in minutes.  Default: 7 days (suitable for web clients
    # storing the token in sessionStorage).
    jwt_expire_minutes: int = 60 * 24 * 7
    # Sentry DSN for error monitoring.  Leave unset (or empty) to disable.
    # Set SENTRY_DSN=https://...@sentry.io/... in .env to enable.
    sentry_dsn: str | None = Field(default=None)
    # Sentry environment tag — defaults to "development" when debug=True and
    # "production" when debug=False so events are bucketed correctly.
    sentry_environment: str | None = Field(default=None)
    # Rate limit applied to /parse and /ingest.
    # Uses slowapi / limits syntax: "N/period" where period is second, minute,
    # hour, or day.  Multiple limits can be joined with ";".
    # Examples: "20/minute", "5/second;100/hour".
    rate_limit_parse: str = "20/minute"
    # Dictionary enrichment: when True, vocabulary objects extracted during
    # /parse are enriched with English glosses from Wiktionary in the background.
    # Disabled by default to avoid external network calls in development and CI.
    # Set ENABLE_DICTIONARY_LOOKUP=true in .env to activate.
    enable_dictionary_lookup: bool = False
    # Machine translation provider.
    # Options: "none" (disabled), "libretranslate", "mymemory".
    # "none" is the safe default — no external translation calls are made.
    # See backend/dictionary/translation.py for attribution and cost details.
    translation_provider: str = "none"
    # Translation API base URL.  Only relevant when translation_provider is
    # "libretranslate".  Defaults to https://libretranslate.com; point at a
    # self-hosted instance for unlimited free use.
    translation_api_url: str | None = None
    # Translation API key.  Optional for LibreTranslate (required on the paid
    # hosted plan); for MyMemory, set this to your registered email to raise
    # the daily quota from 1 000 to 10 000 words.
    translation_api_key: str | None = None
    # When True, vocabulary objects are also enriched with machine translations
    # in the same background pass as dictionary glosses.
    enable_translation_enrichment: bool = False

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @model_validator(mode="after")
    def _reject_wildcard_cors_in_production(self) -> "Settings":
        """Prevent accidental wildcard CORS exposure in production.

        Wildcard CORS is convenient for local development but unsafe when
        DEBUG=False (i.e. in any deployed environment).  This validator turns
        a silent misconfiguration into a hard startup failure so it is caught
        before traffic arrives rather than silently leaking credentials via
        CORS.

        To fix: set CORS_ORIGINS=https://yourapp.example.com in .env.
        Multiple origins are comma-separated.
        """
        if not self.debug and "*" in self.cors_origins:
            raise ValueError(
                "Wildcard CORS origin ('*') is not allowed when DEBUG=False. "
                "Set CORS_ORIGINS to a comma-separated list of specific origins "
                "in your .env file before deploying "
                "(e.g. CORS_ORIGINS=https://yourapp.example.com)."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
