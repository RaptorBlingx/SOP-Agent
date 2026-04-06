"""Upload phase component — file upload and ingestion."""

from __future__ import annotations

import streamlit as st
from frontend.utils.api_client import upload_files


def render_upload_phase() -> None:
    """Render the document upload interface."""
    st.header("📄 Upload SOP Documents")
    st.write("Upload PDF, DOCX, or TXT files containing Standard Operating Procedures.")

    uploaded = st.file_uploader(
        "Choose files",
        type=["pdf", "docx", "txt", "md"],
        accept_multiple_files=True,
        key="file_uploader",
    )

    if uploaded and st.button("Ingest Documents", type="primary"):
        with st.spinner("Ingesting documents..."):
            try:
                result = upload_files(uploaded)
                st.session_state["session_id"] = result["session_id"]
                st.session_state["collection_id"] = result["collection_id"]
                st.session_state["chunks"] = result["total_chunks"]
                st.session_state["phase"] = "task"
                st.success(
                    f"Ingested {len(result['files_processed'])} file(s) — "
                    f"{result['total_chunks']} chunks indexed"
                )
                st.rerun()
            except Exception as exc:
                st.error(f"Ingestion failed: {exc}")
