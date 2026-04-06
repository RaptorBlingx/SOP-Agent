"""Report route — GET /api/v1/report/{session_id} (Section 6.4)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.api.schemas import ReportResponse
from app.core import database as db
from app.core.logging import get_logger
from app.services.report_export import export_markdown

logger = get_logger("api.report")

router = APIRouter(prefix="/api/v1")


@router.get("/report/{session_id}", response_model=ReportResponse)
async def get_report(session_id: str) -> ReportResponse:
    """Retrieve the final execution report for a session."""
    session = await db.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    report = session.get("final_report")
    return ReportResponse(
        session_id=session_id,
        status=session["status"],
        report=report,
    )


@router.get("/report/{session_id}/download")
async def download_report(session_id: str) -> dict:
    """Download the report as a Markdown file."""
    session = await db.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    report = session.get("final_report")
    if not report:
        raise HTTPException(status_code=404, detail="Report not yet generated")

    path = await export_markdown(session_id, report)
    return {"session_id": session_id, "file_path": str(path)}
