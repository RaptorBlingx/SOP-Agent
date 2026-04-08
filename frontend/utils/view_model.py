"""Pure view-model helpers for the Streamlit operator console."""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from typing import Any


@dataclass(frozen=True)
class PhaseDefinition:
    key: str
    label: str
    title: str
    description: str


PHASES: tuple[PhaseDefinition, ...] = (
    PhaseDefinition(
        key="upload",
        label="Upload",
        title="Build your SOP workspace",
        description="Ingest reference documents and create a session-ready knowledge base.",
    ),
    PhaseDefinition(
        key="task",
        label="Define",
        title="Describe the desired outcome",
        description="Give the agent a concrete task and enough context to execute reliably.",
    ),
    PhaseDefinition(
        key="executing",
        label="Execute",
        title="Monitor execution in real time",
        description="Track progress, review state, and intervene only when needed.",
    ),
    PhaseDefinition(
        key="complete",
        label="Report",
        title="Review the final report",
        description="Inspect the run outcome, verify quality, and export the result.",
    ),
)


STATUS_META: dict[str, dict[str, str]] = {
    "planning": {"label": "Planning", "tone": "neutral"},
    "ready": {"label": "Ready", "tone": "info"},
    "executing": {"label": "Executing", "tone": "info"},
    "awaiting_operator": {"label": "Awaiting operator", "tone": "warning"},
    "replanning": {"label": "Replanning", "tone": "warning"},
    "completed": {"label": "Completed", "tone": "success"},
    "failed": {"label": "Failed", "tone": "danger"},
    "deleted": {"label": "Deleted", "tone": "neutral"},
}


def calculate_progress(current_step: int, total_steps: int) -> int:
    """Return a user-facing progress percentage clamped to 0-100."""
    total = max(total_steps, 1)
    current = max(current_step, 0)
    return max(0, min(int(round((current / total) * 100)), 100))


def format_session_label(session_id: str | None) -> str:
    """Return a short, readable session identifier."""
    if not session_id:
        return "Not started"
    if len(session_id) <= 8:
        return session_id
    return f"{session_id[:8]}…"


def format_chunk_summary(chunks: int | None) -> str:
    """Return a readable chunk summary."""
    count = max(chunks or 0, 0)
    noun = "chunk" if count == 1 else "chunks"
    return f"{count} {noun} indexed"


def format_file_size(size_bytes: int | None) -> str:
    """Format a file size in a compact form."""
    size = max(size_bytes or 0, 0)
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{ceil((size / 1024) * 10) / 10:.1f} KB"
    return f"{ceil((size / (1024 * 1024)) * 10) / 10:.1f} MB"


def build_file_inventory(files: list[Any]) -> list[dict[str, str]]:
    """Create a simple file inventory for display."""
    inventory: list[dict[str, str]] = []
    for file in files:
        file_name = getattr(file, "name", "Untitled document")
        extension = file_name.rsplit(".", 1)[-1].upper() if "." in file_name else "FILE"
        inventory.append(
            {
                "name": file_name,
                "type": extension,
                "size": format_file_size(getattr(file, "size", 0)),
            }
        )
    return inventory


def get_status_meta(status: str | None) -> dict[str, str]:
    """Return a status descriptor with safe defaults."""
    if not status:
        return {"label": "Unknown", "tone": "neutral"}
    return STATUS_META.get(status, {"label": status.replace("_", " ").title(), "tone": "neutral"})


def build_phase_steps(current_phase: str) -> list[dict[str, str | bool]]:
    """Build phase-step metadata for a stepper UI."""
    keys = [phase.key for phase in PHASES]
    active_index = keys.index(current_phase) if current_phase in keys else 0
    steps: list[dict[str, str | bool]] = []
    for index, phase in enumerate(PHASES, start=1):
        if index - 1 < active_index:
            state = "complete"
        elif phase.key == current_phase:
            state = "active"
        else:
            state = "upcoming"
        steps.append(
            {
                "key": phase.key,
                "label": phase.label,
                "title": phase.title,
                "description": phase.description,
                "state": state,
                "number": str(index),
                "is_active": phase.key == current_phase,
            }
        )
    return steps


def can_intervene(status: str | None) -> bool:
    """Return whether operator approval controls should be enabled."""
    return status == "awaiting_operator"
