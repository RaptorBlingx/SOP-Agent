"""Async SQLite database layer with WAL mode — all CRUD for the 6 core tables."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import aiosqlite

from contextlib import asynccontextmanager
from typing import AsyncGenerator as _AsyncGen

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger("database")

# ---------------------------------------------------------------------------
# Schema (mirrors scripts/init_db.py — used for runtime init)
# ---------------------------------------------------------------------------

SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    task_description TEXT NOT NULL,
    collection_id TEXT NOT NULL,
    collection_version INTEGER NOT NULL DEFAULT 1,
    reasoning_profile TEXT NOT NULL,
    model_provider TEXT NOT NULL,
    model_name TEXT NOT NULL,
    status TEXT NOT NULL,
    current_step_index INTEGER NOT NULL DEFAULT 0,
    replan_count INTEGER NOT NULL DEFAULT 0,
    awaiting_operator INTEGER NOT NULL DEFAULT 0,
    final_report TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS session_steps (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    step_order INTEGER NOT NULL,
    title TEXT NOT NULL,
    objective TEXT NOT NULL,
    branch_condition TEXT,
    risk_level TEXT NOT NULL,
    requires_approval INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL,
    recommended_action TEXT,
    verification_summary TEXT,
    confidence REAL,
    operator_action TEXT,
    completed_at TEXT,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS step_evidence (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    step_id TEXT NOT NULL,
    chunk_id TEXT NOT NULL,
    source_file TEXT NOT NULL,
    section_path TEXT,
    page_number INTEGER,
    quote TEXT NOT NULL,
    score REAL NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
    FOREIGN KEY (step_id) REFERENCES session_steps(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS approvals (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    step_id TEXT NOT NULL,
    action TEXT NOT NULL,
    reason TEXT,
    override_text TEXT,
    actor TEXT NOT NULL DEFAULT 'operator',
    created_at TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
    FOREIGN KEY (step_id) REFERENCES session_steps(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS run_events (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS ingested_files (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    filename TEXT NOT NULL,
    file_size_bytes INTEGER NOT NULL,
    checksum_sha256 TEXT NOT NULL,
    chunk_count INTEGER NOT NULL,
    ingested_at TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS lexical_chunks (
    id TEXT PRIMARY KEY,
    collection_id TEXT NOT NULL,
    chunk_id TEXT NOT NULL,
    source_file TEXT NOT NULL,
    section_path TEXT,
    page_number INTEGER,
    content TEXT NOT NULL
);

CREATE VIRTUAL TABLE IF NOT EXISTS lexical_chunks_fts USING fts5(
    content,
    content='lexical_chunks',
    content_rowid='rowid'
);

CREATE TRIGGER IF NOT EXISTS lexical_chunks_ai AFTER INSERT ON lexical_chunks BEGIN
    INSERT INTO lexical_chunks_fts(rowid, content) VALUES (new.rowid, new.content);
END;

CREATE TRIGGER IF NOT EXISTS lexical_chunks_ad AFTER DELETE ON lexical_chunks BEGIN
    INSERT INTO lexical_chunks_fts(lexical_chunks_fts, rowid, content) VALUES ('delete', old.rowid, old.content);
END;
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _uuid() -> str:
    return str(uuid4())


@asynccontextmanager
async def get_connection() -> _AsyncGen[aiosqlite.Connection, None]:
    """Open an async SQLite connection with WAL mode and FK enforcement."""
    settings = get_settings()
    Path(settings.database_path).parent.mkdir(parents=True, exist_ok=True)
    conn = await aiosqlite.connect(settings.database_path)
    try:
        conn.row_factory = aiosqlite.Row
        await conn.execute("PRAGMA journal_mode=WAL")
        await conn.execute("PRAGMA foreign_keys=ON")
        yield conn
    finally:
        await conn.close()


async def init_database() -> None:
    """Create all tables if they don't exist."""
    settings = get_settings()
    Path(settings.database_path).parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(settings.database_path)
    db.executescript(SCHEMA)
    db.close()
    logger.info("Database initialized at %s", settings.database_path)


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------

async def create_session(
    task_description: str,
    collection_id: str,
    reasoning_profile: str,
    model_provider: str,
    model_name: str,
    session_id: str | None = None,
) -> dict[str, Any]:
    session_id = session_id or _uuid()
    now = _now()
    async with get_connection() as conn:
        await conn.execute(
            """INSERT INTO sessions
               (id, task_description, collection_id, collection_version,
                reasoning_profile, model_provider, model_name, status,
                current_step_index, replan_count, awaiting_operator,
                created_at, updated_at)
               VALUES (?, ?, ?, 1, ?, ?, ?, 'planning', 0, 0, 0, ?, ?)""",
            (session_id, task_description, collection_id,
             reasoning_profile, model_provider, model_name, now, now),
        )
        await conn.commit()
    return {"session_id": session_id, "created_at": now}


async def get_session(session_id: str) -> dict[str, Any] | None:
    async with get_connection() as conn:
        cursor = await conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None


async def update_session(session_id: str, **fields: Any) -> None:
    fields["updated_at"] = _now()
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [session_id]
    async with get_connection() as conn:
        await conn.execute(
            f"UPDATE sessions SET {set_clause} WHERE id = ?", values
        )
        await conn.commit()


async def delete_session(session_id: str) -> None:
    async with get_connection() as conn:
        await conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        await conn.commit()


# ---------------------------------------------------------------------------
# Steps
# ---------------------------------------------------------------------------

async def create_step(
    session_id: str,
    step_order: int,
    title: str,
    objective: str,
    risk_level: str = "low",
    requires_approval: bool = False,
    branch_condition: str | None = None,
    step_id: str | None = None,
) -> str:
    step_id = step_id or _uuid()
    async with get_connection() as conn:
        await conn.execute(
            """INSERT INTO session_steps
               (id, session_id, step_order, title, objective,
                branch_condition, risk_level, requires_approval, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending')""",
            (step_id, session_id, step_order, title, objective,
             branch_condition, risk_level, int(requires_approval)),
        )
        await conn.commit()
    return step_id


async def get_steps(session_id: str) -> list[dict[str, Any]]:
    async with get_connection() as conn:
        cursor = await conn.execute(
            "SELECT * FROM session_steps WHERE session_id = ? ORDER BY step_order",
            (session_id,),
        )
        return [dict(r) for r in await cursor.fetchall()]


async def update_step(step_id: str, **fields: Any) -> None:
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [step_id]
    async with get_connection() as conn:
        await conn.execute(
            f"UPDATE session_steps SET {set_clause} WHERE id = ?", values
        )
        await conn.commit()


# ---------------------------------------------------------------------------
# Evidence
# ---------------------------------------------------------------------------

async def add_evidence(
    session_id: str,
    step_id: str,
    chunk_id: str,
    source_file: str,
    quote: str,
    score: float,
    section_path: str | None = None,
    page_number: int | None = None,
) -> str:
    eid = _uuid()
    async with get_connection() as conn:
        await conn.execute(
            """INSERT INTO step_evidence
               (id, session_id, step_id, chunk_id, source_file,
                section_path, page_number, quote, score, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (eid, session_id, step_id, chunk_id, source_file,
             section_path, page_number, quote, score, _now()),
        )
        await conn.commit()
    return eid


async def get_evidence_for_step(step_id: str) -> list[dict[str, Any]]:
    async with get_connection() as conn:
        cursor = await conn.execute(
            "SELECT * FROM step_evidence WHERE step_id = ? ORDER BY score DESC",
            (step_id,),
        )
        return [dict(r) for r in await cursor.fetchall()]


# ---------------------------------------------------------------------------
# Approvals
# ---------------------------------------------------------------------------

async def record_approval(
    session_id: str,
    step_id: str,
    action: str,
    reason: str | None = None,
    override_text: str | None = None,
    actor: str = "operator",
) -> str:
    aid = _uuid()
    async with get_connection() as conn:
        await conn.execute(
            """INSERT INTO approvals
               (id, session_id, step_id, action, reason, override_text, actor, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (aid, session_id, step_id, action, reason, override_text, actor, _now()),
        )
        await conn.commit()
    return aid


async def get_approvals(session_id: str) -> list[dict[str, Any]]:
    async with get_connection() as conn:
        cursor = await conn.execute(
            "SELECT * FROM approvals WHERE session_id = ? ORDER BY created_at",
            (session_id,),
        )
        return [dict(r) for r in await cursor.fetchall()]


# ---------------------------------------------------------------------------
# Run Events
# ---------------------------------------------------------------------------

async def add_run_event(
    session_id: str,
    event_type: str,
    payload: dict[str, Any] | None = None,
) -> str:
    eid = _uuid()
    async with get_connection() as conn:
        await conn.execute(
            """INSERT INTO run_events (id, session_id, event_type, payload_json, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (eid, session_id, event_type, json.dumps(payload or {}), _now()),
        )
        await conn.commit()
    return eid


async def get_run_events(session_id: str) -> list[dict[str, Any]]:
    async with get_connection() as conn:
        cursor = await conn.execute(
            "SELECT * FROM run_events WHERE session_id = ? ORDER BY created_at",
            (session_id,),
        )
        rows = [dict(r) for r in await cursor.fetchall()]
        for r in rows:
            r["payload"] = json.loads(r.pop("payload_json", "{}"))
        return rows


# ---------------------------------------------------------------------------
# Ingested Files
# ---------------------------------------------------------------------------

async def record_ingestion(
    session_id: str,
    filename: str,
    file_size_bytes: int,
    checksum_sha256: str,
    chunk_count: int,
) -> str:
    fid = _uuid()
    async with get_connection() as conn:
        await conn.execute(
            """INSERT INTO ingested_files
               (id, session_id, filename, file_size_bytes, checksum_sha256, chunk_count, ingested_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (fid, session_id, filename, file_size_bytes, checksum_sha256, chunk_count, _now()),
        )
        await conn.commit()
    return fid


async def get_ingested_files(session_id: str) -> list[dict[str, Any]]:
    async with get_connection() as conn:
        cursor = await conn.execute(
            "SELECT * FROM ingested_files WHERE session_id = ? ORDER BY ingested_at",
            (session_id,),
        )
        return [dict(r) for r in await cursor.fetchall()]


# ---------------------------------------------------------------------------
# Lexical Chunks (for FTS5 search)
# ---------------------------------------------------------------------------

async def store_lexical_chunk(
    collection_id: str,
    chunk_id: str,
    source_file: str,
    content: str,
    section_path: str | None = None,
    page_number: int | None = None,
) -> str:
    lid = _uuid()
    async with get_connection() as conn:
        await conn.execute(
            """INSERT INTO lexical_chunks
               (id, collection_id, chunk_id, source_file, section_path, page_number, content)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (lid, collection_id, chunk_id, source_file, section_path, page_number, content),
        )
        await conn.commit()
    return lid


async def lexical_fts_search(
    query: str,
    collection_id: str,
    k: int = 8,
) -> list[dict[str, Any]]:
    """BM25 search via FTS5."""
    async with get_connection() as conn:
        cursor = await conn.execute(
            """SELECT lc.*, rank
               FROM lexical_chunks_fts fts
               JOIN lexical_chunks lc ON lc.rowid = fts.rowid
               WHERE lexical_chunks_fts MATCH ?
                 AND lc.collection_id = ?
               ORDER BY rank
               LIMIT ?""",
            (query, collection_id, k),
        )
        return [dict(r) for r in await cursor.fetchall()]


async def delete_lexical_chunks(collection_id: str) -> None:
    async with get_connection() as conn:
        await conn.execute(
            "DELETE FROM lexical_chunks WHERE collection_id = ?",
            (collection_id,),
        )
        await conn.commit()
