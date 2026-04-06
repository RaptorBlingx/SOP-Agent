"""SOP Agent — Operator Console (Section 8).

Streamlit frontend with 4 phases:
1. Upload — ingest SOP documents
2. Task — enter task description
3. Executing — monitor progress + operator controls
4. Complete — view/download report
"""

from __future__ import annotations

import streamlit as st
from frontend.utils.api_client import DEFAULT_API_URL

st.set_page_config(
    page_title="SOP Agent Console",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Sidebar ---
with st.sidebar:
    st.title("📋 SOP Agent")
    st.caption("v1.2.0 — AI-powered SOP Execution")

    api_url = st.text_input("API URL", value=DEFAULT_API_URL, key="api_url")
    st.divider()

    # Backend health check
    from frontend.utils.api_client import health_check
    if health_check():
        st.success("Backend: Connected")
    else:
        st.error("Backend: Unreachable")

    st.divider()

    # Session info
    if "session_id" in st.session_state:
        st.info(f"Session: `{st.session_state['session_id'][:8]}...`")
        st.write(f"Phase: **{st.session_state.get('phase', 'upload')}**")

    # Session list
    st.subheader("Recent Sessions")
    try:
        from frontend.utils.api_client import list_sessions
        sessions = list_sessions()
        for s in sessions[:5]:
            status_icon = {"completed": "✅", "executing": "⚙️", "failed": "❌"}.get(s["status"], "⬜")
            if st.button(f"{status_icon} {s['session_id'][:8]}...", key=f"sess_{s['session_id']}"):
                st.session_state["session_id"] = s["session_id"]
                if s["status"] == "completed":
                    st.session_state["phase"] = "complete"
                elif s["status"] == "executing":
                    st.session_state["phase"] = "executing"
                else:
                    st.session_state["phase"] = "task"
                st.rerun()
    except Exception:
        st.caption("No sessions found")

# --- Initialize phase ---
if "phase" not in st.session_state:
    st.session_state["phase"] = "upload"

# --- Route to phase ---
phase = st.session_state["phase"]

if phase == "upload":
    from frontend.components.upload import render_upload_phase
    render_upload_phase()

elif phase == "task":
    from frontend.components.task_input import render_task_phase
    render_task_phase()

elif phase == "executing":
    from frontend.components.execution_monitor import render_execution_phase
    render_execution_phase()

elif phase == "complete":
    from frontend.components.report_viewer import render_report_phase
    render_report_phase()
