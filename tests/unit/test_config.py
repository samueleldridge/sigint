"""Tests for application configuration."""

from __future__ import annotations

import pytest

from sigint.config import Settings


def test_settings_with_required_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    """Settings can be instantiated when required env vars are set."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    settings = Settings()
    assert settings.OPENAI_API_KEY == "sk-test-key"


def test_database_url_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """DATABASE_URL has the expected default value."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    settings = Settings()
    assert settings.DATABASE_URL == "postgresql://sigint:sigint@localhost:5432/sigint"
