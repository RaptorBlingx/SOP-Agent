"""Unit tests for routing functions."""

import pytest
from app.agents.state import AgentState, ExecutionStep, ApprovalRequest


def _make_state(**overrides) -> AgentState:
    defaults = {
        "session_id": "test",
        "task_description": "Test task",
        "collection_id": "col-test",
        "status": "executing",
        "current_step_index": 0,
        "steps": [],
        "replan_count": 0,
    }
    defaults.update(overrides)
    return AgentState(**defaults)


def test_route_from_intake_new_session():
    from app.agents.routing import route_from_intake
    state = _make_state(current_step_index=0, steps=[])
    assert route_from_intake(state) == "planner"


def test_route_from_intake_resume():
    from app.agents.routing import route_from_intake
    step = ExecutionStep(step_id="s1", order=1, title="T", objective="O")
    state = _make_state(current_step_index=1, steps=[step])
    assert route_from_intake(state) == "evidence_router"


def test_route_from_intake_replan():
    from app.agents.routing import route_from_intake
    state = _make_state(status="replanning")
    assert route_from_intake(state) == "replanner"


def test_route_from_verifier_continue():
    from app.agents.routing import route_from_verifier
    step = ExecutionStep(step_id="s1", order=1, title="T", objective="O")
    state = _make_state(steps=[step, step], current_step_index=1)
    assert route_from_verifier(state) == "evidence_router"


def test_route_from_verifier_approval():
    from app.agents.routing import route_from_verifier
    approval = ApprovalRequest(request_id="r1", step_id="s1", reason="test", severity="medium")
    state = _make_state(pending_approval=approval)
    assert route_from_verifier(state) == "approval_gate"


def test_route_from_verifier_complete():
    from app.agents.routing import route_from_verifier
    step = ExecutionStep(step_id="s1", order=1, title="T", objective="O")
    state = _make_state(steps=[step], current_step_index=1)
    assert route_from_verifier(state) == "reporter"


def test_route_from_verifier_failed():
    from app.agents.routing import route_from_verifier
    state = _make_state(status="failed")
    assert route_from_verifier(state) == "reporter"


def test_route_from_approval_gate_continue():
    from app.agents.routing import route_from_approval_gate
    step = ExecutionStep(step_id="s1", order=1, title="T", objective="O")
    state = _make_state(steps=[step, step], current_step_index=1)
    assert route_from_approval_gate(state) == "evidence_router"


def test_route_from_approval_gate_abort():
    from app.agents.routing import route_from_approval_gate
    state = _make_state(status="failed")
    assert route_from_approval_gate(state) == "reporter"


def test_route_from_replanner_continue():
    from app.agents.routing import route_from_replanner
    step = ExecutionStep(step_id="s1", order=1, title="T", objective="O")
    state = _make_state(steps=[step], current_step_index=0)
    assert route_from_replanner(state) == "evidence_router"
