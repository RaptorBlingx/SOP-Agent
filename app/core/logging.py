"""Structured logging with PII/secret redaction per spec Section 13.5."""

from __future__ import annotations

import logging
import re
import sys

# Patterns that should be redacted from log output
_REDACT_PATTERNS = [
    (re.compile(r'(api[_-]?key\s*[=:]\s*)["\']?[\w\-]{20,}["\']?', re.IGNORECASE), r'\1[REDACTED]'),
    (re.compile(r'(bearer\s+)[\w\-\.]{20,}', re.IGNORECASE), r'\1[REDACTED]'),
    (re.compile(r'sk-[\w\-]{10,}'), '[REDACTED_KEY]'),
    (re.compile(r'AIza[\w\-]{30,}'), '[REDACTED_KEY]'),
]


class RedactingFormatter(logging.Formatter):
    """Log formatter that redacts sensitive patterns."""

    def format(self, record: logging.LogRecord) -> str:
        message = super().format(record)
        for pattern, replacement in _REDACT_PATTERNS:
            message = pattern.sub(replacement, message)
        return message


def setup_logging(level: str = "INFO") -> logging.Logger:
    """Configure application-wide structured logging."""
    root = logging.getLogger("sop_agent")
    if root.handlers:
        return root

    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(root.level)

    formatter = RedactingFormatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    handler.setFormatter(formatter)
    root.addHandler(handler)

    return root


def get_logger(name: str) -> logging.Logger:
    """Get a child logger under the sop_agent namespace."""
    return logging.getLogger(f"sop_agent.{name}")
