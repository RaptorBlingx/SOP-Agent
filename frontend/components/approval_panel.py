"""Approval panel component — detailed approval UI."""

from __future__ import annotations

import streamlit as st
from frontend.utils.api_client import send_intervention


def render_approval_panel(session_id: str, approval_data: dict | None = None) -> None:
    """Render the approval decision panel."""
    st.subheader("🟡 Approval Required")

    if approval_data:
        st.warning(f"**Step:** {approval_data.get('step_id', 'N/A')}")
        st.write(f"**Reason:** {approval_data.get('reason', 'No reason provided')}")
        st.write(f"**Severity:** {approval_data.get('severity', 'medium')}")
        st.write(f"**Confidence:** {approval_data.get('confidence', 'N/A')}")

        if approval_data.get("recommendation"):
            with st.expander("Recommended Action"):
                st.write(approval_data["recommendation"])

        if approval_data.get("evidence"):
            with st.expander("Supporting Evidence"):
                for ref in approval_data["evidence"]:
                    st.markdown(f"- **{ref.get('source', 'Unknown')}** (score: {ref.get('score', 0):.2f})")
                    st.caption(ref.get("snippet", ""))

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("✅ Approve", key="approval_approve", type="primary", use_container_width=True):
            _do_action(session_id, "approve")

    with col2:
        if st.button("⏭️ Skip", key="approval_skip", use_container_width=True):
            _do_action(session_id, "skip")

    with col3:
        if st.button("🛑 Abort", key="approval_abort", use_container_width=True):
            _do_action(session_id, "abort")

    override_text = st.text_area("Override instruction:", key="approval_override_text")
    if override_text and st.button("📝 Apply Override", key="approval_override"):
        _do_action(session_id, "override", override_text)


def _do_action(session_id: str, action: str, override_text: str | None = None) -> None:
    try:
        result = send_intervention(session_id, action, override_text)
        st.success(f"{action.title()} applied")
        st.rerun()
    except Exception as exc:
        st.error(f"Failed: {exc}")
