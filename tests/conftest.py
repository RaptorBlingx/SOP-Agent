"""Shared test fixtures and configuration."""

from __future__ import annotations

import os
import asyncio
import sqlite3
from pathlib import Path

import pytest

# Set test environment before any app imports
os.environ.setdefault("MODEL_PROVIDER", "ollama")
os.environ.setdefault("EMBEDDING_PROVIDER", "ollama")
os.environ.setdefault("OLLAMA_BASE_URL", "http://localhost:11434")
os.environ.setdefault("DATABASE_PATH", "")
os.environ.setdefault("CHROMADB_PATH", "")
os.environ.setdefault("UPLOAD_PATH", "")


@pytest.fixture(scope="session")
def event_loop():
    """Create a session-scoped event loop."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def tmp_data_dir(tmp_path: Path) -> Path:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    return data_dir


@pytest.fixture
def tmp_db_path(tmp_data_dir: Path) -> Path:
    return tmp_data_dir / "test.db"


@pytest.fixture
def mock_settings(tmp_data_dir: Path, tmp_db_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_db_path))
    monkeypatch.setenv("CHROMADB_PATH", str(tmp_data_dir / "chromadb"))
    monkeypatch.setenv("UPLOAD_PATH", str(tmp_data_dir / "uploads"))
    monkeypatch.setenv("MODEL_PROVIDER", "ollama")
    monkeypatch.setenv("EMBEDDING_PROVIDER", "ollama")

    from app.core.config import get_settings
    get_settings.cache_clear()
    settings = get_settings()
    settings.ensure_directories()
    return settings


@pytest.fixture
def initialized_db(mock_settings, tmp_db_path: Path):
    from app.core.database import SCHEMA
    conn = sqlite3.connect(str(tmp_db_path))
    conn.executescript(SCHEMA)
    conn.close()
    return tmp_db_path


@pytest.fixture
def sample_sop_text() -> str:
    return """# Employee Onboarding SOP

## 1. Pre-Arrival Preparation
1.1 Send welcome email to new hire with start date and required documents.
1.2 Prepare workstation with necessary equipment and software.
1.3 Create accounts in HR system, email, and team collaboration tools.

## 2. Day One Activities
2.1 Conduct facility tour and introduce team members.
2.2 Review company policies and sign required documents.
2.3 Set up IT access and verify all systems are working.

## 3. First Week Training
3.1 Assign mentor and schedule daily check-ins.
3.2 Complete mandatory compliance training modules.
3.3 Review role-specific procedures and expectations.

## 4. 30-Day Review
4.1 Conduct performance check-in with manager.
4.2 Gather feedback from new hire on onboarding experience.
4.3 Adjust training plan based on progress.
"""
