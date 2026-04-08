"""Shared UI primitives for the Streamlit operator console."""

from __future__ import annotations

import html

import streamlit as st

from frontend.utils.view_model import build_phase_steps, get_status_meta


_THEME_CSS = """
<style>
    .stApp {
        background:
            radial-gradient(circle at top left, rgba(80, 122, 255, 0.16), transparent 28%),
            radial-gradient(circle at top right, rgba(45, 212, 191, 0.12), transparent 24%),
            linear-gradient(180deg, #07111f 0%, #0b1324 100%);
        color: #f3f6fb;
    }

    [data-testid="stSidebar"] {
        background: rgba(6, 15, 29, 0.88);
        border-right: 1px solid rgba(148, 163, 184, 0.12);
    }

    [data-testid="stHeader"] {
        background: transparent;
    }

    [data-testid="stAppViewContainer"] > .main {
        padding-top: 1.25rem;
    }

    div[data-testid="stMetric"] {
        background: rgba(11, 19, 36, 0.75);
        border: 1px solid rgba(148, 163, 184, 0.16);
        border-radius: 18px;
        padding: 0.9rem 1rem;
        box-shadow: 0 16px 40px rgba(15, 23, 42, 0.18);
    }

    div[data-testid="stMetric"] label {
        color: #94a3b8;
    }

    .stButton > button, .stDownloadButton > button {
        min-height: 2.75rem;
        border-radius: 14px;
        font-weight: 600;
        border: 1px solid rgba(148, 163, 184, 0.2);
    }

    .stTextInput input, .stTextArea textarea {
        border-radius: 14px;
    }

    .stFileUploader {
        background: rgba(11, 19, 36, 0.4);
        border-radius: 18px;
        padding: 0.4rem;
    }

    .sa-hero {
        padding: 1.4rem 1.5rem;
        border-radius: 24px;
        background:
            linear-gradient(135deg, rgba(30, 41, 59, 0.94), rgba(15, 23, 42, 0.9));
        border: 1px solid rgba(148, 163, 184, 0.16);
        box-shadow: 0 24px 60px rgba(2, 8, 23, 0.24);
        margin-bottom: 1rem;
    }

    .sa-eyebrow {
        text-transform: uppercase;
        letter-spacing: 0.12em;
        font-size: 0.74rem;
        font-weight: 700;
        color: #7dd3fc;
        margin-bottom: 0.45rem;
    }

    .sa-hero h1 {
        margin: 0;
        font-size: clamp(1.8rem, 4vw, 2.6rem);
        line-height: 1.08;
    }

    .sa-hero p {
        margin: 0.65rem 0 0;
        color: #cbd5e1;
        font-size: 1rem;
        max-width: 46rem;
    }

    .sa-badge-row {
        display: flex;
        flex-wrap: wrap;
        gap: 0.5rem;
        margin-top: 0.95rem;
    }

    .sa-badge {
        display: inline-flex;
        align-items: center;
        gap: 0.35rem;
        border-radius: 999px;
        padding: 0.38rem 0.72rem;
        font-size: 0.82rem;
        font-weight: 600;
        border: 1px solid rgba(148, 163, 184, 0.18);
        background: rgba(15, 23, 42, 0.62);
        color: #e2e8f0;
    }

    .sa-badge[data-tone="success"] {
        color: #bbf7d0;
        background: rgba(20, 83, 45, 0.48);
    }

    .sa-badge[data-tone="warning"] {
        color: #fde68a;
        background: rgba(120, 53, 15, 0.46);
    }

    .sa-badge[data-tone="danger"] {
        color: #fecaca;
        background: rgba(127, 29, 29, 0.48);
    }

    .sa-badge[data-tone="info"] {
        color: #bfdbfe;
        background: rgba(30, 64, 175, 0.42);
    }

    .sa-section-title {
        margin: 1.4rem 0 0.4rem;
        font-size: 1.05rem;
        font-weight: 700;
        color: #f8fafc;
    }

    .sa-section-copy {
        margin: 0 0 1rem;
        color: #94a3b8;
        font-size: 0.95rem;
    }

    .sa-stepper {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 0.75rem;
        margin: 1rem 0 1.5rem;
    }

    .sa-step {
        padding: 0.95rem 1rem;
        border-radius: 18px;
        background: rgba(11, 19, 36, 0.56);
        border: 1px solid rgba(148, 163, 184, 0.14);
    }

    .sa-step[data-state="active"] {
        border-color: rgba(96, 165, 250, 0.7);
        background: rgba(15, 23, 42, 0.92);
    }

    .sa-step[data-state="complete"] {
        background: rgba(20, 83, 45, 0.26);
        border-color: rgba(74, 222, 128, 0.28);
    }

    .sa-step-number {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 1.8rem;
        height: 1.8rem;
        border-radius: 999px;
        background: rgba(96, 165, 250, 0.12);
        color: #bfdbfe;
        font-size: 0.85rem;
        font-weight: 700;
        margin-bottom: 0.55rem;
    }

    .sa-step-label {
        font-weight: 700;
        color: #f8fafc;
        margin-bottom: 0.22rem;
    }

    .sa-step-description {
        color: #94a3b8;
        font-size: 0.82rem;
        line-height: 1.35;
    }

    .sa-note {
        border-left: 3px solid rgba(125, 211, 252, 0.7);
        background: rgba(8, 47, 73, 0.42);
        color: #dbeafe;
        padding: 0.9rem 1rem;
        border-radius: 14px;
        margin-bottom: 1rem;
    }

    @media (max-width: 900px) {
        .sa-stepper {
            grid-template-columns: 1fr 1fr;
        }
    }

    @media (max-width: 640px) {
        .sa-stepper {
            grid-template-columns: 1fr;
        }
    }
</style>
"""


def apply_theme() -> None:
    """Inject the shared theme."""
    st.markdown(_THEME_CSS, unsafe_allow_html=True)


def render_hero(
    eyebrow: str,
    title: str,
    description: str,
    badges: list[tuple[str, str]] | None = None,
) -> None:
    """Render a premium page hero."""
    badge_markup = ""
    if badges:
        badge_markup = '<div class="sa-badge-row">' + "".join(
            f'<span class="sa-badge" data-tone="{html.escape(tone)}">{html.escape(label)}</span>'
            for label, tone in badges
        ) + "</div>"

    st.markdown(
        f"""
        <section class="sa-hero">
            <div class="sa-eyebrow">{html.escape(eyebrow)}</div>
            <h1>{html.escape(title)}</h1>
            <p>{html.escape(description)}</p>
            {badge_markup}
        </section>
        """,
        unsafe_allow_html=True,
    )


def render_section_heading(title: str, description: str) -> None:
    """Render a consistent section heading."""
    st.markdown(
        f"""
        <div class="sa-section-title">{html.escape(title)}</div>
        <p class="sa-section-copy">{html.escape(description)}</p>
        """,
        unsafe_allow_html=True,
    )


def render_note(message: str) -> None:
    """Render an inline informational note."""
    st.markdown(f'<div class="sa-note">{html.escape(message)}</div>', unsafe_allow_html=True)


def render_phase_stepper(current_phase: str) -> None:
    """Render the workflow stepper."""
    step_markup = "".join(
        f'<div class="sa-step" data-state="{html.escape(str(step["state"]))}">'
        f'<div class="sa-step-number">{html.escape(str(step["number"]))}</div>'
        f'<div class="sa-step-label">{html.escape(str(step["label"]))}</div>'
        f'<div class="sa-step-description">{html.escape(str(step["description"]))}</div>'
        "</div>"
        for step in build_phase_steps(current_phase)
    )
    st.markdown(f'<div class="sa-stepper">{step_markup}</div>', unsafe_allow_html=True)


def render_status_badge(status: str | None) -> None:
    """Render the current run status badge."""
    meta = get_status_meta(status)
    st.markdown(
        f'<span class="sa-badge" data-tone="{html.escape(meta["tone"])}">{html.escape(meta["label"])}</span>',
        unsafe_allow_html=True,
    )
