"""Upload phase component — file upload and ingestion."""

from __future__ import annotations

import streamlit as st

from frontend.components.ui import render_hero, render_note, render_section_heading
from frontend.utils.api_client import upload_files
from frontend.utils.view_model import build_file_inventory, format_chunk_summary

SUPPORTED_FILE_TYPES = ["pdf", "docx", "txt", "md"]


def render_upload_phase() -> None:
    """Render the document upload interface."""
    render_hero(
        eyebrow="Phase 1 · Upload",
        title="Create a reliable SOP knowledge base",
        description=(
            "Start with the source of truth. Upload the SOPs your operators depend on so the "
            "agent can reason over a current, searchable document set."
        ),
        badges=[
            ("PDF, DOCX, TXT, MD", "info"),
            ("Batch upload", "neutral"),
            ("Session-ready indexing", "success"),
        ],
    )

    render_note(
        "Well-structured documents lead to better plans, safer recommendations, and fewer "
        "operator interventions downstream."
    )

    col_primary, col_guidance = st.columns((1.35, 0.85), gap="large")

    with col_primary:
        render_section_heading(
            "Source documents",
            "Use the latest approved SOPs. You can upload multiple files in one pass.",
        )
        uploaded = st.file_uploader(
            "Choose files",
            type=SUPPORTED_FILE_TYPES,
            accept_multiple_files=True,
            key="file_uploader",
            label_visibility="collapsed",
        )

        if uploaded:
            st.caption(f"Selected {len(uploaded)} file(s)")
            inventory = build_file_inventory(uploaded)
            for item in inventory:
                st.markdown(
                    f"**{item['name']}**  \n"
                    f"<span class='sa-badge'>{item['type']}</span> "
                    f"<span class='sa-badge'>{item['size']}</span>",
                    unsafe_allow_html=True,
                )

        if st.button(
            "Ingest documents",
            type="primary",
            use_container_width=True,
            disabled=not uploaded,
        ):
            with st.spinner("Ingesting documents..."):
                try:
                    result = upload_files(uploaded)
                    st.session_state["session_id"] = result["session_id"]
                    st.session_state["collection_id"] = result["collection_id"]
                    st.session_state["chunks"] = result["total_chunks"]
                    st.session_state["phase"] = "task"
                    st.success(
                        f"Ingested {len(result['files_processed'])} file(s) — "
                        f"{format_chunk_summary(result['total_chunks'])}"
                    )
                    st.rerun()
                except Exception as exc:
                    st.error(f"Ingestion failed: {exc}")

    with col_guidance:
        render_section_heading(
            "What good input looks like",
            "A small amount of preparation dramatically improves output quality.",
        )
        st.markdown(
            "- Use approved SOPs rather than drafts\n"
            "- Keep filenames specific and traceable\n"
            "- Prefer one procedure per document when possible\n"
            "- Include markdown or text exports for faster parsing"
        )
        st.metric("Supported formats", str(len(SUPPORTED_FILE_TYPES)))
        st.metric("Recommended upload mode", "Batch")
