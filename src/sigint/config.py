"""Application configuration loaded from environment variables."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration for the sigint application."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    DATABASE_URL: str = "postgresql://sigint:sigint@localhost:5432/sigint"
    OPENAI_API_KEY: str
    OPENAI_MODEL: str = "gpt-5.4-mini"
    LOG_LEVEL: str = "INFO"
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    FRED_API_KEY: str | None = None
