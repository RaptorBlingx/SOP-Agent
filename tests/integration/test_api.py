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


def test_execute_awaiting_operator_requires_intervention(api_client, event_loop):
    from app.core import database as db

    session_id = "awaiting-operator-session"
    event_loop.run_until_complete(db.create_session(
        session_id=session_id,
        task_description="Handle incident",
        collection_id=f"sop_{session_id}",
        reasoning_profile="balanced",
        model_provider="ollama",
        model_name="qwen3.5:9b",
    ))
    step_id = event_loop.run_until_complete(db.create_step(
        session_id=session_id,
        step_id=f"{session_id}_step_1",
        step_order=1,
        title="Review",
        objective="Needs operator approval",
        risk_level="medium",
        requires_approval=True,
    ))
    event_loop.run_until_complete(db.update_step(step_id, status="needs_approval"))
    event_loop.run_until_complete(db.update_session(
        session_id,
        status="awaiting_operator",
        awaiting_operator=1,
    ))

    resp = api_client.post("/api/v1/execute", json={
        "session_id": session_id,
        "task_description": "Handle incident",
    })

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "awaiting_operator"
    assert "awaiting operator action" in data["message"].lower()


def test_intervene_approve_uses_pending_step_and_resumes(api_client, event_loop, monkeypatch):
    from app.core import database as db

    session_id = "approval-resume-session"
    event_loop.run_until_complete(db.create_session(
        session_id=session_id,
        task_description="Handle incident",
        collection_id=f"sop_{session_id}",
        reasoning_profile="balanced",
        model_provider="ollama",
        model_name="qwen3.5:9b",
    ))
    step_id = event_loop.run_until_complete(db.create_step(
        session_id=session_id,
        step_id=f"{session_id}_step_1",
        step_order=1,
        title="Review",
        objective="Needs operator approval",
        risk_level="medium",
        requires_approval=True,
    ))
    event_loop.run_until_complete(db.update_step(step_id, status="needs_approval"))
    event_loop.run_until_complete(db.update_session(
        session_id,
        status="awaiting_operator",
        awaiting_operator=1,
    ))
    event_loop.run_until_complete(db.add_run_event(
        session_id,
        "awaiting_operator",
        {"step_id": step_id, "reason": "Needs review"},
    ))

    resumed: dict[str, str] = {}

    def fake_enqueue_run(resume_session_id: str, task_description: str) -> None:
        resumed["session_id"] = resume_session_id
        resumed["task_description"] = task_description

    monkeypatch.setattr("app.api.routes.intervene._enqueue_run", fake_enqueue_run)

    resp = api_client.post("/api/v1/intervene", json={
        "session_id": session_id,
        "action": "approve",
    })

    assert resp.status_code == 200
    assert resumed == {
        "session_id": session_id,
        "task_description": "Handle incident",
    }

    session = event_loop.run_until_complete(db.get_session(session_id))
    steps = event_loop.run_until_complete(db.get_steps(session_id))
    approvals = event_loop.run_until_complete(db.get_approvals(session_id))

    assert session["status"] == "executing"
    assert session["awaiting_operator"] == 0
    assert steps[0]["status"] == "completed"
    assert steps[0]["operator_action"] == "approve"
    assert approvals[0]["step_id"] == step_id
    assert approvals[0]["reason"] == "Needs review"
