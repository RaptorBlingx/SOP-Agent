"""Unit tests for app.core.config."""

import pytest


def test_settings_loads_defaults(mock_settings):
    assert mock_settings.model_provider in ("gemini", "openai", "anthropic", "ollama")
    assert mock_settings.database_path != ""


def test_settings_ensure_directories(mock_settings):
    from pathlib import Path
    mock_settings.ensure_directories()
    assert Path(mock_settings.database_path).parent.exists()


def test_settings_singleton(mock_settings):
    from app.core.config import get_settings
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2
