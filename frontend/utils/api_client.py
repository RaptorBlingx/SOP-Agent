"""API client for Streamlit frontend."""

from __future__ import annotations

import os
import httpx
from typing import Any, AsyncGenerator

LOCAL_API_URL = "http://localhost:8000"

# Default backend URL — Streamlit runs server-side, so localhost is preferred in Codespaces.
DEFAULT_API_URL = os.environ.get("BACKEND_URL", LOCAL_API_URL)


def _normalize_api_url(url: str) -> str:
    """Prefer localhost for server-side Streamlit calls inside GitHub Codespaces."""
    if os.environ.get("CODESPACES", "").lower() == "true" and ".app.github.dev" in url:
        return LOCAL_API_URL
    return url


def get_display_api_url() -> str:
    import streamlit as st

    configured = st.session_state.get("api_url", DEFAULT_API_URL)
    return _normalize_api_url(configured)


def get_api_url() -> str:
    import streamlit as st
    configured = st.session_state.get("api_url", DEFAULT_API_URL)
    return _normalize_api_url(configured)


def sync_client() -> httpx.Client:
    return httpx.Client(base_url=get_api_url(), timeout=60.0)


async def async_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=get_api_url(), timeout=60.0)


def health_check() -> bool:
    try:
        with sync_client() as client:
            resp = client.get("/health")
            return resp.status_code == 200
    except Exception:
        return False


def upload_files(files: list[Any], session_id: str | None = None) -> dict:
    """Upload files to the ingest endpoint."""
    with sync_client() as client:
        file_tuples = [("files", (f.name, f.getvalue(), "application/octet-stream")) for f in files]
        data = {}
        if session_id:
            data["session_id"] = session_id
        resp = client.post("/api/v1/ingest", files=file_tuples, data=data)
        resp.raise_for_status()
        return resp.json()


def start_execution(session_id: str, task_description: str) -> dict:
    """Start SOP execution."""
    with sync_client() as client:
        resp = client.post("/api/v1/execute", json={
            "session_id": session_id,
            "task_description": task_description,
        })
        resp.raise_for_status()
        return resp.json()


def send_intervention(session_id: str, action: str, override_text: str | None = None) -> dict:
    """Send operator intervention."""
    with sync_client() as client:
        payload: dict[str, Any] = {
            "session_id": session_id,
            "action": action,
        }
        if override_text:
            payload["override_text"] = override_text
        resp = client.post("/api/v1/intervene", json=payload)
        resp.raise_for_status()
        return resp.json()


def get_report(session_id: str) -> dict:
    """Get execution report."""
    with sync_client() as client:
        resp = client.get(f"/api/v1/report/{session_id}")
        resp.raise_for_status()
        return resp.json()


def get_session(session_id: str) -> dict:
    """Get session details."""
    with sync_client() as client:
        resp = client.get(f"/api/v1/sessions/{session_id}")
        resp.raise_for_status()
        return resp.json()


def list_sessions() -> list[dict]:
    """List all sessions."""
    with sync_client() as client:
        resp = client.get("/api/v1/sessions")
        resp.raise_for_status()
        return resp.json().get("sessions", [])
