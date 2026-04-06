"""Unit tests for agent state models."""

import pytest


def test_execution_step_defaults():
    from app.agents.state import ExecutionStep

    step = ExecutionStep(step_id="s1", order=1, title="Test", objective="Do thing")
    assert step.status == "pending"
    assert step.risk_level == "low"
    assert step.confidence is None


def test_execution_step_valid_statuses():
    from app.agents.state import ExecutionStep

    valid = ["pending", "ready", "executing", "completed",
             "needs_approval", "replanned", "skipped", "failed"]
    for status in valid:
        step = ExecutionStep(step_id="s1", order=1, title="T", objective="O", status=status)
        assert step.status == status


def test_plan_schema():
    from app.agents.state import PlanSchema, ExecutionStep

    plan = PlanSchema(steps=[
        ExecutionStep(step_id="s1", order=1, title="A", objective="Do A"),
        ExecutionStep(step_id="s2", order=2, title="B", objective="Do B"),
    ])
    assert len(plan.steps) == 2


def test_evidence_ref():
    from app.agents.state import EvidenceRef

    ref = EvidenceRef(chunk_id="c1", source_file="doc.pdf", quote="text here", score=0.88)
    assert ref.score == 0.88
    assert ref.source_file == "doc.pdf"


def test_approval_request():
    from app.agents.state import ApprovalRequest

    req = ApprovalRequest(
        request_id="req-1",
        step_id="s1",
        reason="High risk action",
        severity="high",
    )
    assert req.severity == "high"


def test_agent_state_defaults():
    from app.agents.state import AgentState

    state = AgentState(session_id="test", task_description="Do stuff", collection_id="col-1")
    assert state.status == "planning"
    assert state.current_step_index == 0
    assert state.replan_count == 0
    assert state.steps == []
