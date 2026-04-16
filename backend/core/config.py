from functools import lru_cache

from pydantic import Field
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
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])
    # Maximum number of characters accepted by /parse and /ingest before the
    # NLP pipeline is invoked.  Protects against event-loop blocking on large
    # pastes.  Set MAX_PARSE_CHARS in .env to override.
    max_parse_chars: int = 10_000

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
