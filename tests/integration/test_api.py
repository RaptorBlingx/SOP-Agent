"""Integration tests for API routes."""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def api_client(mock_settings, initialized_db):
    from app.core.config import get_settings
    get_settings.cache_clear()

    from app.main import create_app
    app = create_app()
    return TestClient(app)


def test_health_check(api_client):
    resp = api_client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["version"] == "1.2.0"


def test_list_sessions_empty(api_client):
    resp = api_client.get("/api/v1/sessions")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data["sessions"], list)


def test_get_session_not_found(api_client):
    resp = api_client.get("/api/v1/sessions/nonexistent")
    assert resp.status_code == 404


def test_get_report_not_found(api_client):
    resp = api_client.get("/api/v1/report/nonexistent")
    assert resp.status_code == 404


def test_execute_not_found(api_client):
    resp = api_client.post("/api/v1/execute", json={
        "session_id": "nonexistent",
        "task_description": "test",
    })
    assert resp.status_code == 404


def test_intervene_invalid_action(api_client):
    resp = api_client.post("/api/v1/intervene", json={
        "session_id": "test",
        "action": "invalid_action",
    })
    assert resp.status_code == 400
