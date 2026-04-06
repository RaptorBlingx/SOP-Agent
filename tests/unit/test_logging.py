"""Unit tests for logging with PII redaction."""

import pytest
import logging


def test_pii_redaction():
    from app.core.logging import RedactingFormatter

    formatter = RedactingFormatter(fmt="%(message)s")

    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname="", lineno=0,
        msg="Key is sk-proj-abc123def456ghi789 and token Bearer eyJhbGciOiJIUzI1NiIBBCC",
        args=(), exc_info=None,
    )

    output = formatter.format(record)
    assert "sk-proj-abc123def456ghi789" not in output
    assert "REDACTED" in output


def test_get_logger():
    from app.core.logging import get_logger

    logger = get_logger("test.module")
    assert logger.name == "sop_agent.test.module"
