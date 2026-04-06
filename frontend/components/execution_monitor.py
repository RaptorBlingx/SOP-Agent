"""Execution monitor component — real-time progress with SSE."""

from __future__ import annotations

import streamlit as st
from frontend.utils.api_client import get_session, send_intervention
from frontend.utils.sse_listener import listen_sse


def render_execution_phase() -> None:
    """Render the execution monitoring view."""
    st.header("⚙️ Execution Monitor")

    session_id = st.session_state.get("session_id", "")
    st.info(f"Session: `{session_id}`")

    # Status area
    status_container = st.container()
    progress_bar = st.progress(0)
    event_log = st.expander("Event Log", expanded=True)

    # Check current state
    try:
        session = get_session(session_id)
        total = session.get("total_steps", 1) or 1
        current = session.get("current_step_index", 0)
        progress_bar.progress(min(current / total, 1.0))

        with status_container:
            st.metric("Status", session.get("status", "unknown"))
            col1, col2 = st.columns(2)
            col1.metric("Steps", f"{current}/{total}")
            col2.metric("Progress", f"{int(current / total * 100)}%")

        if session.get("status") == "completed":
            st.session_state["phase"] = "complete"
            st.rerun()

    except Exception as exc:
        st.warning(f"Could not fetch session: {exc}")

    # Approval controls
    st.subheader("Operator Controls")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        if st.button("✅ Approve", use_container_width=True):
            _send_action(session_id, "approve")

    with col2:
        if st.button("⏭️ Skip", use_container_width=True):
            _send_action(session_id, "skip")

    with col3:
        if st.button("🔄 Replan", use_container_width=True):
            _send_action(session_id, "request_replan")

    with col4:
        if st.button("🛑 Abort", use_container_width=True):
            _send_action(session_id, "abort")

    # Override text
    override = st.text_input("Override instruction (for override action):")
    if override and st.button("📝 Override"):
        _send_action(session_id, "override", override)

    # Refresh button
    if st.button("🔃 Refresh"):
        st.rerun()


def _send_action(session_id: str, action: str, override_text: str | None = None) -> None:
    try:
        result = send_intervention(session_id, action, override_text)
        st.success(f"Action '{action}' applied: {result.get('message', 'OK')}")
        st.rerun()
    except Exception as exc:
        st.error(f"Intervention failed: {exc}")
