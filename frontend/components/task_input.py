"""Task input component — enter SOP task description."""

from __future__ import annotations

import streamlit as st

from frontend.components.ui import render_hero, render_note, render_section_heading
from frontend.utils.api_client import start_execution
from frontend.utils.view_model import format_chunk_summary, format_session_label


def render_task_phase() -> None:
    """Render the task description input."""
    session_id = st.session_state.get("session_id", "")
    chunk_summary = format_chunk_summary(st.session_state.get("chunks", 0))

    render_hero(
        eyebrow="Phase 2 · Define",
        title="Give the agent a concrete objective",
        description=(
            "The strongest tasks are outcome-focused and precise. Make the goal explicit so the "
            "agent can translate SOP knowledge into a dependable execution plan."
        ),
        badges=[
            (f"Session {format_session_label(session_id)}", "info"),
            (chunk_summary, "success"),
        ],
    )

    render_note(
        "Avoid vague prompts. Define the desired workflow, important constraints, and the level "
        "of detail you expect in the final output."
    )

    col_main, col_examples = st.columns((1.4, 0.8), gap="large")

    with col_main:
        render_section_heading(
            "Task brief",
            "Describe the procedure to execute, the expected outcome, and any guardrails.",
        )
        task = st.text_area(
            "Describe the SOP task to execute:",
            placeholder="Walk me through the employee onboarding process step by step, flagging any step that requires manager approval.",
            height=180,
            key="task_input",
            label_visibility="collapsed",
        )

        primary_col, secondary_col = st.columns((1, 1))
        with primary_col:
            if st.button(
                "Start execution",
                type="primary",
                use_container_width=True,
                disabled=not bool(task.strip()),
            ):
                with st.spinner("Starting execution..."):
                    try:
                        result = start_execution(session_id, task)
                        st.session_state["task_description"] = task
                        st.session_state["phase"] = "executing"
                        st.success(f"Execution started: {result.get('message', 'OK')}")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Failed to start: {exc}")

        with secondary_col:
            if st.button("Back to upload", use_container_width=True):
                st.session_state["phase"] = "upload"
                st.rerun()

    with col_examples:
        render_section_heading(
            "Prompting guidance",
            "Use outcome-oriented briefs that are easy to verify.",
        )
        st.markdown(
            "**Strong examples**\n\n"
            "- Execute the laptop offboarding SOP and highlight any security-sensitive steps.\n"
            "- Walk me through incident triage, but pause when a step requires director approval.\n"
            "- Summarize the travel reimbursement workflow into a concise operator checklist."
        )
        st.metric("Expected operator friction", "Low")
        st.metric("Best prompt style", "Specific")
