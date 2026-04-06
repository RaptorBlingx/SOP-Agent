"""Policy thresholds — configurable confidence gates per risk level (Section 5.6)."""

from __future__ import annotations

# Confidence thresholds below which a step requires operator approval
CONFIDENCE_THRESHOLDS = {
    "low": 0.6,
    "medium": 0.75,
    "high": 0.9,
}

# Maximum replan attempts before forcing approval
MAX_REPLAN_ATTEMPTS = 3

# Evidence pack minimum size — below this the verifier should flag weak evidence
MIN_EVIDENCE_PACK_SIZE = 1

# Minimum evidence score to be considered valid
MIN_EVIDENCE_SCORE = 0.3


def confidence_requires_approval(confidence: float, risk_level: str) -> bool:
    """Check if the confidence score falls below the threshold for the risk level."""
    threshold = CONFIDENCE_THRESHOLDS.get(risk_level, CONFIDENCE_THRESHOLDS["medium"])
    return confidence < threshold


def evidence_is_weak(evidence_count: int, min_score: float = 0.0) -> bool:
    """Check if the evidence pack is too small or low-quality."""
    if evidence_count < MIN_EVIDENCE_PACK_SIZE:
        return True
    if min_score > 0 and min_score < MIN_EVIDENCE_SCORE:
        return True
    return False
