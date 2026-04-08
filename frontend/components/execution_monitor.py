"""Execution monitor component — real-time progress with SSE."""

from __future__ import annotations

import streamlit as st

from frontend.components.ui import render_hero, render_note, render_section_heading, render_status_badge
from frontend.utils.api_client import get_session, send_intervention
from frontend.utils.view_model import calculate_progress, can_intervene, format_session_label, get_status_meta


def render_execution_phase() -> None:
    """Render the execution monitoring view."""
    session_id = st.session_state.get("session_id", "")
    session: dict | None = None

    # Check current state
    try:
        session = get_session(session_id)
        if session.get("status") == "completed":
            st.session_state["phase"] = "complete"
            st.rerun()
    except Exception as exc:
        st.warning(f"Could not fetch session: {exc}")

    session = session or {}
    status = session.get("status", "unknown")
    total_steps = session.get("total_steps", 0)
    current_step = session.get("current_step_index", 0)
    display_total_steps = max(total_steps, 1)
    progress = calculate_progress(current_step, total_steps)
    status_meta = get_status_meta(status)

    render_hero(
        eyebrow="Phase 3 · Execute",
        title="Monitor progress without losing context",
        description=(
            "This workspace keeps execution state, operator actions, and progress visible at a "
            "glance so you can step in only when judgment is required."
        ),
        badges=[
            (f"Session {format_session_label(session_id)}", "info"),
            (status_meta["label"], status_meta["tone"]),
            (f"{progress}% complete", "success" if progress == 100 else "info"),
        ],
    )

    if status == "awaiting_operator":
        render_note("Execution is paused for operator input. Review the current state, then approve, skip, override, or abort.")
    elif status == "replanning":
        render_note("The agent is revising the plan based on operator guidance or verification feedback.")
    else:
        render_note("Use refresh to pull the latest state. Operator interventions are enabled only when the run is awaiting approval.")

    metric_col1, metric_col2, metric_col3 = st.columns(3)
    metric_col1.metric("Status", status_meta["label"])
    metric_col2.metric("Steps", f"{current_step}/{display_total_steps}")
    metric_col3.metric("Progress", f"{progress}%")
    st.progress(progress / 100)

    col_main, col_controls = st.columns((1.15, 0.85), gap="large")

    with col_main:
        render_section_heading(
            "Execution summary",
            "A compact view of current run state and next expected operator behavior.",
        )
        st.markdown(f"**Current status**")
        render_status_badge(status)
        st.markdown("")
        st.markdown(
            f"- **Current step index:** {current_step}\n"
            f"- **Total planned steps:** {total_steps}\n"
            f"- **Task brief:** {st.session_state.get('task_description', 'Not captured')}"
        )

        with st.expander("Operational guidance", expanded=status == "awaiting_operator"):
            st.markdown(
                "- Approve when the recommendation is safe and aligned with policy.\n"
                "- Skip when the step is unnecessary in the current scenario.\n"
                "- Override when you need to inject explicit human judgment.\n"
                "- Request replan when the approach is directionally wrong."
            )

    with col_controls:
        render_section_heading(
            "Operator controls",
            "Use interventions deliberately to keep the run explainable and safe.",
        )
        approval_enabled = can_intervene(status)

        col1, col2 = st.columns(2)
        with col1:
            if st.button(
                "Approve",
                use_container_width=True,
                type="primary",
                disabled=not approval_enabled,
            ):
                _send_action(session_id, "approve")

        with col2:
            if st.button("Skip", use_container_width=True, disabled=not approval_enabled):
                _send_action(session_id, "skip")

        col3, col4 = st.columns(2)
        with col3:
            if st.button("Request replan", use_container_width=True):
                _send_action(session_id, "request_replan")

        with col4:
            if st.button("Abort", use_container_width=True):
                _send_action(session_id, "abort")

        override = st.text_area(
            "Override instruction",
            placeholder="Provide the exact instruction the agent should follow instead.",
            height=100,
        )
        if st.button(
            "Apply override",
            use_container_width=True,
            disabled=not approval_enabled or not bool(override.strip()),
        ):
            _send_action(session_id, "override", override)

        if st.button("Refresh state", use_container_width=True):
            st.rerun()


def _send_action(session_id: str, action: str, override_text: str | None = None) -> None:
    try:
        result = send_intervention(session_id, action, override_text)
        st.success(f"Action '{action}' applied: {result.get('message', 'OK')}")
        st.rerun()
    except Exception as exc:
        st.error(f"Intervention failed: {exc}")
