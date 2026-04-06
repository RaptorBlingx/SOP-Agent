"""Ingest route — POST /api/v1/ingest (Section 6.1).

Accepts multipart file uploads, runs ingestion pipeline.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, Form, HTTPException

from app.api.schemas import IngestResponse
from app.services.ingestion import ingest_files
from app.core.logging import get_logger

logger = get_logger("api.ingest")

router = APIRouter(prefix="/api/v1")


@router.post("/ingest", response_model=IngestResponse)
async def ingest_documents(
    files: list[UploadFile] = File(...),
    session_id: str | None = Form(None),
    collection_name: str | None = Form(None),
) -> IngestResponse:
    """Upload and ingest SOP documents."""
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    sid = session_id or str(uuid.uuid4())

    file_tuples: list[tuple[str, bytes]] = []
    for upload in files:
        if upload.filename is None:
            raise HTTPException(status_code=400, detail="File must have a filename")
        safe_name = Path(upload.filename).name
        content = await upload.read()
        file_tuples.append((safe_name, content))

    try:
        result = await ingest_files(
            files=file_tuples,
            session_id=sid,
            collection_id=collection_name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("Ingestion failed")
        raise HTTPException(status_code=500, detail=f"Ingestion error: {exc}")

    return IngestResponse(**result)
