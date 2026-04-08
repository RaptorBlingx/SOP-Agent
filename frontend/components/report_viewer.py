"""Report viewer component — display final execution report."""

from __future__ import annotations

import streamlit as st

from frontend.components.ui import render_hero, render_note, render_section_heading
from frontend.utils.api_client import get_report
from frontend.utils.view_model import format_session_label, get_status_meta


def render_report_phase() -> None:
    """Render the final report view."""
    session_id = st.session_state.get("session_id", "")

    try:
        data = get_report(session_id)
        status = data.get("status", "unknown")
        report = data.get("report")
        status_meta = get_status_meta(status)

        render_hero(
            eyebrow="Phase 4 · Report",
            title="Review the execution outcome",
            description=(
                "Use the final report to validate the run, share a structured summary, and "
                "archive the result for downstream operators."
            ),
            badges=[
                (f"Session {format_session_label(session_id)}", "info"),
                (status_meta["label"], status_meta["tone"]),
            ],
        )

        if report:
            render_note("Review the rendered summary first, then use the raw markdown view when you need to copy, diff, or export the exact output.")
        else:
            render_note("The report has not been generated yet. If the run is still in progress, return to the execution workspace and refresh the current state.")

        if report:
            metric_col1, metric_col2 = st.columns(2)
            metric_col1.metric("Final status", status_meta["label"])
            metric_col2.metric("Report length", f"{len(report.splitlines())} lines")

            render_section_heading(
                "Execution report",
                "Rendered preview for fast review, plus raw markdown for export and auditing.",
            )
            preview_tab, markdown_tab = st.tabs(["Preview", "Markdown"])
            with preview_tab:
                st.markdown(report)
            with markdown_tab:
                st.code(report, language="markdown")

            action_col1, action_col2 = st.columns((1, 1))
            with action_col1:
                st.download_button(
                    label="Download markdown report",
                    data=report,
                    file_name=f"report_{session_id}.md",
                    mime="text/markdown",
                    use_container_width=True,
                )
            with action_col2:
                if st.button("Start a new session", use_container_width=True):
                    _reset_session()
        else:
            st.warning("Report not yet available. Execution may still be in progress.")

    except Exception as exc:
        st.error(f"Failed to load report: {exc}")
        if st.button("Return to execution", use_container_width=True):
            st.session_state["phase"] = "executing"
            st.rerun()


def _reset_session() -> None:
    for key in ["session_id", "collection_id", "chunks", "task_description", "phase"]:
        st.session_state.pop(key, None)
    st.rerun()
