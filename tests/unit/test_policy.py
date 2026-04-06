"""Unit tests for policy modules."""

import pytest


def test_confidence_requires_approval():
    from app.policy.thresholds import confidence_requires_approval

    assert confidence_requires_approval(0.5, "high") is True
    assert confidence_requires_approval(0.95, "high") is False
    assert confidence_requires_approval(0.5, "low") is True
    assert confidence_requires_approval(0.7, "low") is False


def test_evidence_is_weak():
    from app.policy.thresholds import evidence_is_weak

    assert evidence_is_weak(0) is True   # no evidence
    assert evidence_is_weak(1) is False   # has evidence
    assert evidence_is_weak(1, min_score=0.1) is True  # low min_score
    assert evidence_is_weak(1, min_score=0.5) is False


def test_step_requires_approval_high_risk():
    from app.policy.approval_rules import step_requires_approval
    from app.agents.state import ExecutionStep, EvidenceRef

    step = ExecutionStep(
        step_id="s1", order=1, title="Deploy", objective="Deploy to production",
        risk_level="high",
    )
    evidence = [EvidenceRef(chunk_id="c1", source_file="f", quote="q", score=0.9)]
    requires, reason = step_requires_approval(step, confidence=0.95, evidence=evidence)
    assert requires is True
    assert reason is not None


def test_step_requires_approval_low_confidence():
    from app.policy.approval_rules import step_requires_approval
    from app.agents.state import ExecutionStep, EvidenceRef

    step = ExecutionStep(
        step_id="s1", order=1, title="Review", objective="Review docs",
        risk_level="low",
    )
    evidence = [EvidenceRef(chunk_id="c1", source_file="f", quote="q", score=0.9)]
    requires, reason = step_requires_approval(step, confidence=0.3, evidence=evidence)
    assert requires is True


def test_step_requires_approval_irreversible():
    from app.policy.approval_rules import step_requires_approval
    from app.agents.state import ExecutionStep, EvidenceRef

    step = ExecutionStep(
        step_id="s1", order=1, title="Delete records",
        objective="Permanently delete all old records",
        risk_level="low",
    )
    evidence = [EvidenceRef(chunk_id="c1", source_file="f", quote="q", score=0.9)]
    requires, reason = step_requires_approval(step, confidence=0.95, evidence=evidence)
    assert requires is True


def test_determine_severity():
    from app.policy.approval_rules import determine_severity
    from app.agents.state import ExecutionStep

    high = ExecutionStep(step_id="s1", order=1, title="T", objective="O", risk_level="high")
    low = ExecutionStep(step_id="s2", order=2, title="T", objective="O", risk_level="low")

    assert determine_severity(high, 0.3) == "critical"
    assert determine_severity(low, 0.9) == "medium"


def test_should_replan():
    from app.policy.approval_rules import should_replan

    assert should_replan(replan_count=0, verification_outcome="replan") is True
    assert should_replan(replan_count=3, verification_outcome="replan") is False
    assert should_replan(replan_count=0, verification_outcome="continue") is False
