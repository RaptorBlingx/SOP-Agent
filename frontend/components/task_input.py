"""Task input component — enter SOP task description."""

from __future__ import annotations

import streamlit as st
from frontend.utils.api_client import start_execution


def render_task_phase() -> None:
    """Render the task description input."""
    st.header("📋 Define Task")

    session_id = st.session_state.get("session_id", "")
    st.info(f"Session: `{session_id}` — {st.session_state.get('chunks', 0)} chunks indexed")

    task = st.text_area(
        "Describe the SOP task to execute:",
        placeholder="e.g., Walk me through the employee onboarding process step by step",
        height=120,
        key="task_input",
    )

    if task and st.button("Start Execution", type="primary"):
        with st.spinner("Starting execution..."):
            try:
                result = start_execution(session_id, task)
                st.session_state["task_description"] = task
                st.session_state["phase"] = "executing"
                st.success(f"Execution started: {result.get('message', 'OK')}")
                st.rerun()
            except Exception as exc:
                st.error(f"Failed to start: {exc}")

    if st.button("← Back to Upload"):
        st.session_state["phase"] = "upload"
        st.rerun()
