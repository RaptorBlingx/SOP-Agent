"""Initialize the SOP Agent SQLite database with the required schema."""

import sqlite3
import os
import sys

DATABASE_PATH = os.getenv("DATABASE_PATH", "./data/sop_agent.db")

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

-- FTS5 virtual table for lexical (BM25) search
CREATE VIRTUAL TABLE IF NOT EXISTS lexical_chunks_fts USING fts5(
    content,
    content='lexical_chunks',
    content_rowid='rowid'
);

-- Triggers to keep FTS index in sync
CREATE TRIGGER IF NOT EXISTS lexical_chunks_ai AFTER INSERT ON lexical_chunks BEGIN
    INSERT INTO lexical_chunks_fts(rowid, content)
    VALUES (new.rowid, new.content);
END;

CREATE TRIGGER IF NOT EXISTS lexical_chunks_ad AFTER DELETE ON lexical_chunks BEGIN
    INSERT INTO lexical_chunks_fts(lexical_chunks_fts, rowid, content)
    VALUES ('delete', old.rowid, old.content);
END;
"""


def init_db():
    os.makedirs(os.path.dirname(DATABASE_PATH) or ".", exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH)
    conn.executescript(SCHEMA)
    conn.close()
    print(f"Database initialized at {DATABASE_PATH}")


if __name__ == "__main__":
    init_db()
    sys.exit(0)
