"""SOP Agent — Operator Console (Section 8).

Streamlit frontend with 4 phases:
1. Upload — ingest SOP documents
2. Task — enter task description
3. Executing — monitor progress + operator controls
4. Complete — view/download report
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import streamlit as st

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from frontend.components.ui import apply_theme, render_phase_stepper
from frontend.utils.api_client import LOCAL_API_URL, get_display_api_url

st.set_page_config(
    page_title="SOP Agent Console",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded",
)
apply_theme()

# --- Sidebar ---
with st.sidebar:
    st.title("📋 SOP Agent")
    st.caption("Production console for SOP-driven execution")

    if "api_url" not in st.session_state:
        st.session_state["api_url"] = get_display_api_url()
    elif os.environ.get("CODESPACES", "").lower() == "true" and ".app.github.dev" in st.session_state["api_url"]:
        st.session_state["api_url"] = LOCAL_API_URL

    st.text_input("Backend endpoint", key="api_url", help="Base URL for the FastAPI backend.")
    if os.environ.get("CODESPACES", "").lower() == "true":
        st.caption("In GitHub Codespaces, the Streamlit server should use http://localhost:8000 to reach the backend.")
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
        st.caption("Current workspace")
        st.code(st.session_state["session_id"], language=None)
        st.write(f"Phase: **{st.session_state.get('phase', 'upload').title()}**")

    # Session list
    st.subheader("Recent Sessions")
    try:
        from frontend.utils.api_client import list_sessions
        sessions = list_sessions()
        for s in sessions[:5]:
            status_icon = {
                "completed": "✅",
                "executing": "⚙️",
                "awaiting_operator": "🟡",
                "replanning": "🔄",
                "failed": "❌",
            }.get(s["status"], "⬜")
            label = f"{status_icon} {s['session_id'][:8]} · {s['status'].replace('_', ' ')}"
            if st.button(label, key=f"sess_{s['session_id']}", use_container_width=True):
                st.session_state["session_id"] = s["session_id"]
                if s["status"] == "completed":
                    st.session_state["phase"] = "complete"
                elif s["status"] in ("executing", "awaiting_operator", "replanning"):
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
render_phase_stepper(phase)

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
