from __future__ import annotations

from types import SimpleNamespace

from frontend.utils.view_model import (
    build_file_inventory,
    build_phase_steps,
    calculate_progress,
    can_intervene,
    format_chunk_summary,
    format_file_size,
    format_session_label,
    get_status_meta,
)


def test_calculate_progress_clamps_values() -> None:
    assert calculate_progress(-1, 0) == 0
    assert calculate_progress(1, 4) == 25
    assert calculate_progress(9, 4) == 100


def test_build_phase_steps_marks_active_and_completed_states() -> None:
    steps = build_phase_steps("executing")

    assert [step["state"] for step in steps] == ["complete", "complete", "active", "upcoming"]
    assert steps[2]["is_active"] is True


def test_status_helpers_and_intervention_gate() -> None:
    assert get_status_meta("awaiting_operator") == {"label": "Awaiting operator", "tone": "warning"}
    assert get_status_meta("custom_status") == {"label": "Custom Status", "tone": "neutral"}
    assert can_intervene("awaiting_operator") is True
    assert can_intervene("executing") is False


def test_formatting_helpers_for_session_chunks_and_files() -> None:
    files = [
        SimpleNamespace(name="handbook.pdf", size=2048),
        SimpleNamespace(name="checklist.txt", size=999),
    ]

    inventory = build_file_inventory(files)

    assert format_session_label("1234567890") == "12345678…"
    assert format_chunk_summary(1) == "1 chunk indexed"
    assert format_chunk_summary(2) == "2 chunks indexed"
    assert format_file_size(2048) == "2.0 KB"
    assert inventory == [
        {"name": "handbook.pdf", "type": "PDF", "size": "2.0 KB"},
        {"name": "checklist.txt", "type": "TXT", "size": "999 B"},
    ]
