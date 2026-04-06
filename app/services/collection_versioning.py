"""Collection versioning for re-ingestion tracking (Section 6.4)."""

from __future__ import annotations

from typing import Any

from app.core import database as db
from app.core.logging import get_logger

logger = get_logger("services.collection_versioning")

# In-memory version tracker (backed by session table's collection_version column)
_versions: dict[str, int] = {}


async def get_collection_version(session_id: str) -> int:
    """Get the current collection version for a session."""
    if session_id in _versions:
        return _versions[session_id]
    session = await db.get_session(session_id)
    if session:
        version = session.get("collection_version", 1)
        _versions[session_id] = version
        return version
    return 1


async def increment_collection_version(session_id: str) -> int:
    """Increment the collection version (used on re-ingestion)."""
    current = await get_collection_version(session_id)
    new_version = current + 1
    await db.update_session(session_id, collection_version=new_version)
    _versions[session_id] = new_version
    logger.info("Collection version for session %s: %d -> %d", session_id, current, new_version)
    return new_version
