"""Report viewer component — display final execution report."""

from __future__ import annotations

import streamlit as st
from frontend.utils.api_client import get_report


def render_report_phase() -> None:
    """Render the final report view."""
    st.header("📊 Execution Report")

    session_id = st.session_state.get("session_id", "")

    try:
        data = get_report(session_id)
        status = data.get("status", "unknown")
        report = data.get("report")

        st.metric("Final Status", status)

        if report:
            st.markdown(report)

            st.download_button(
                label="📥 Download Report (Markdown)",
                data=report,
                file_name=f"report_{session_id}.md",
                mime="text/markdown",
            )
        else:
            st.warning("Report not yet available. Execution may still be in progress.")

    except Exception as exc:
        st.error(f"Failed to load report: {exc}")

    if st.button("🔄 New Session"):
        for key in ["session_id", "collection_id", "chunks", "task_description", "phase"]:
            st.session_state.pop(key, None)
        st.rerun()
