"""Session management routes — GET/DELETE /api/v1/sessions (Section 6.5)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.api.schemas import SessionInfo, SessionListResponse
from app.core import database as db
from app.core.logging import get_logger

logger = get_logger("api.session")


def _dict_factory(cursor, row):
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}


router = APIRouter(prefix="/api/v1")


@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions() -> SessionListResponse:
    """List all sessions."""
    from app.core.database import get_connection

    async with get_connection() as conn:
        conn.row_factory = _dict_factory
        cursor = await conn.execute(
            "SELECT id, status, collection_id, created_at FROM sessions ORDER BY created_at DESC"
        )
        rows = await cursor.fetchall()

    sessions = []
    for row in rows:
        steps = await db.get_steps(row["id"])
        current_idx = 0
        for i, s in enumerate(steps):
            if s.get("status") not in ("completed", "skipped"):
                current_idx = i
                break
        else:
            current_idx = len(steps)

        sessions.append(SessionInfo(
            session_id=row["id"],
            status=row["status"],
            collection_id=row["collection_id"],
            total_steps=len(steps),
            current_step_index=current_idx,
            created_at=row["created_at"],
        ))

    return SessionListResponse(sessions=sessions)


@router.get("/sessions/{session_id}", response_model=SessionInfo)
async def get_session(session_id: str) -> SessionInfo:
    """Get session details."""
    session = await db.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    steps = await db.get_steps(session_id)
    current_idx = 0
    for i, s in enumerate(steps):
        if s.get("status") not in ("completed", "skipped"):
            current_idx = i
            break
    else:
        current_idx = len(steps)

    return SessionInfo(
        session_id=session_id,
        status=session["status"],
        collection_id=session.get("collection_id"),
        total_steps=len(steps),
        current_step_index=current_idx,
        created_at=session.get("created_at"),
    )


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str) -> dict:
    """Delete a session and its data."""
    session = await db.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    await db.delete_session(session_id)
    logger.info("Session %s deleted", session_id)
    return {"status": "deleted", "session_id": session_id}
