"""API request/response schemas (Section 6)."""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


# --- Ingestion ---

class IngestRequest(BaseModel):
    session_id: str | None = Field(None, description="Existing session to add files to")
    collection_name: str | None = Field(None, description="Custom collection name")


class IngestResponse(BaseModel):
    session_id: str
    collection_id: str
    collection_version: int = 1
    total_chunks: int
    files_processed: list[str]
    status: str = "ready"


# --- Execution ---

class ExecuteRequest(BaseModel):
    session_id: str = Field(..., description="Session with ingested documents")
    task_description: str = Field(..., description="Natural-language SOP task")


class ExecutionEvent(BaseModel):
    event_type: str
    data: dict[str, Any]


class ExecuteResponse(BaseModel):
    session_id: str
    status: str
    message: str


# --- Intervention ---

class InterventionRequest(BaseModel):
    session_id: str = Field(..., description="Session requiring intervention")
    action: str = Field(..., description="approve | override | skip | abort | request_replan")
    override_text: str | None = Field(None, description="Override instruction text")


class InterventionResponse(BaseModel):
    session_id: str
    status: str
    message: str


# --- Report ---

class ReportResponse(BaseModel):
    session_id: str
    status: str
    report: str | None = None


# --- Session ---

class SessionInfo(BaseModel):
    session_id: str
    status: str
    collection_id: str | None = None
    total_steps: int = 0
    current_step_index: int = 0
    created_at: str | None = None


class SessionListResponse(BaseModel):
    sessions: list[SessionInfo]


# --- Health ---

class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "1.2.0"


# --- Errors ---

class ErrorResponse(BaseModel):
    detail: str
