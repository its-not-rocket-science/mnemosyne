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
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
