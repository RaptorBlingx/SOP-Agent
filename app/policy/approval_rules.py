"""Approval rules engine — when to require operator intervention (Section 5.6).

The runtime pauses only when at least one trigger is true:
- The step implies an irreversible external action
- The evidence pack is weak or contradictory
- The confidence score falls below the policy threshold
- The SOP explicitly requires approval
- The operator manually intervenes
"""

from __future__ import annotations

import re
from typing import Any

from app.policy.thresholds import (
    confidence_requires_approval,
    evidence_is_weak,
    MAX_REPLAN_ATTEMPTS,
)
from app.agents.state import ExecutionStep, EvidenceRef


# Keywords that suggest irreversible or high-stakes actions
IRREVERSIBLE_KEYWORDS = [
    "delete", "remove", "terminate", "fire", "cancel",
    "payment", "transfer", "sign", "approve", "authorize",
    "deploy", "publish", "send", "submit", "execute",
    "legal", "compliance", "financial", "manager approval",
]


def step_requires_approval(
    step: ExecutionStep,
    evidence: list[EvidenceRef],
    confidence: float | None = None,
) -> tuple[bool, str | None]:
    """Determine if a step requires operator approval.

    Returns (requires_approval: bool, reason: str | None).
    """
    reasons: list[str] = []

    # 1. Step explicitly flagged
    if step.requires_approval:
        reasons.append("Step is flagged as requiring approval in the execution plan")

    # 2. High risk level
    if step.risk_level == "high":
        reasons.append("Step is classified as high-risk")

    # 3. Confidence below threshold
    effective_confidence = confidence if confidence is not None else (step.confidence or 0.0)
    if confidence_requires_approval(effective_confidence, step.risk_level):
        reasons.append(
            f"Confidence {effective_confidence:.2f} is below threshold for {step.risk_level}-risk step"
        )

    # 4. Weak evidence
    if evidence_is_weak(len(evidence)):
        reasons.append(f"Evidence pack is weak ({len(evidence)} items)")

    # 5. Irreversible action detected in step text
    step_text = f"{step.title} {step.objective} {step.recommended_action or ''}".lower()
    for keyword in IRREVERSIBLE_KEYWORDS:
        if keyword in step_text:
            reasons.append(f"Potentially irreversible action detected: '{keyword}'")
            break

    if reasons:
        return True, "; ".join(reasons)
    return False, None


def determine_severity(
    step: ExecutionStep,
    confidence: float | None = None,
) -> str:
    """Determine the severity level for an approval request."""
    effective_confidence = confidence if confidence is not None else (step.confidence or 0.0)

    if step.risk_level == "high" or effective_confidence < 0.4:
        return "critical"
    elif step.risk_level == "medium" or effective_confidence < 0.6:
        return "high"
    return "medium"


def should_replan(
    replan_count: int,
    verification_outcome: str,
) -> bool:
    """Determine if a replan should be attempted vs escalating to approval."""
    if replan_count >= MAX_REPLAN_ATTEMPTS:
        return False  # Too many replans; escalate to approval
    return verification_outcome == "replan"
