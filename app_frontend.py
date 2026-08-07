"""
app_frontend.py

World-class Streamlit frontend for the AI Cohort Interview Agent.

Sections:
  - Sidebar  : API config, candidate selector, bio card, KPI metrics, session reset.
  - Main Top : Candidate learning timeline / competency map (coloured mission badges).
  - Main Mid : Real-time chat interface (st.chat_message / st.chat_input).
  - Main Bot : Conditional "Technical Readiness Assessment" feedback panel + Markdown export.

Run:
    streamlit run app_frontend.py
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
import streamlit as st

# ──────────────────────────────────────────────────────────────────────────────
# Page config (MUST be first Streamlit call)
# ──────────────────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="AI Cohort · Interview Agent",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ──────────────────────────────────────────────────────────────────────────────
# Global CSS – polished dark-mode aesthetic
# ──────────────────────────────────────────────────────────────────────────────

st.markdown(
    """
    <style>
    /* ── Base & fonts ─────────────────────────────────────────────── */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

    /* ── Sidebar ───────────────────────────────────────────────────── */
    section[data-testid="stSidebar"] { background: #0d1117; border-right: 1px solid #21262d; }
    section[data-testid="stSidebar"] * { color: #e6edf3 !important; }

    /* ── Bio card ──────────────────────────────────────────────────── */
    .bio-card {
        background: linear-gradient(135deg, #161b22, #1c2128);
        border: 1px solid #30363d;
        border-radius: 12px;
        padding: 16px 18px;
        margin-bottom: 14px;
    }
    .bio-title { font-size: 17px; font-weight: 700; color: #58a6ff; margin-bottom: 4px; }
    .bio-sub   { font-size: 13px; color: #8b949e; margin-bottom: 10px; }
    .bio-row   { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 6px; }
    .bio-badge {
        background: #21262d; border: 1px solid #30363d;
        border-radius: 6px; padding: 3px 9px;
        font-size: 12px; color: #c9d1d9;
    }
    .badge-green  { background: #0d4b20; border-color: #238636; color: #3fb950; }
    .badge-blue   { background: #0c2d6b; border-color: #1f6feb; color: #58a6ff; }

    /* ── KPI metrics ───────────────────────────────────────────────── */
    .kpi-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-top: 10px; }
    .kpi-card {
        background: #161b22; border: 1px solid #30363d; border-radius: 10px;
        padding: 12px 8px; text-align: center;
    }
    .kpi-val  { font-size: 22px; font-weight: 700; color: #58a6ff; }
    .kpi-lbl  { font-size: 11px; color: #8b949e; margin-top: 2px; }

    /* ── Mission badges ────────────────────────────────────────────── */
    .mission-grid { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 20px; }
    .mission-pill {
        border-radius: 20px; padding: 5px 12px;
        font-size: 12px; font-weight: 500;
        border: 1px solid transparent;
        white-space: nowrap;
    }
    .pill-pass   { background: #0d4b20; border-color: #238636; color: #3fb950; }
    .pill-skip   { background: #2d2208; border-color: #9e6a03; color: #d29922; }
    .pill-fail   { background: #3d0c0c; border-color: #da3633; color: #f85149; }

    /* ── Chat bubbles ──────────────────────────────────────────────── */
    [data-testid="stChatMessage"] { border-radius: 12px; margin-bottom: 6px; }

    /* ── Feedback panel ────────────────────────────────────────────── */
    .panel-header {
        background: linear-gradient(90deg, #0c2d6b, #0d4b20);
        border-radius: 12px 12px 0 0;
        padding: 18px 24px;
        margin-bottom: 0;
    }
    .panel-title { font-size: 22px; font-weight: 700; color: #fff; margin: 0; }
    .panel-sub   { font-size: 13px; color: #8b949e; margin-top: 4px; }

    .summary-box {
        background: #161b22; border-left: 4px solid #58a6ff;
        border-radius: 0 8px 8px 0; padding: 16px 20px;
        margin: 16px 0; color: #c9d1d9; line-height: 1.7;
    }

    .strength-card {
        background: #0d4b20; border: 1px solid #238636;
        border-radius: 10px; padding: 12px 14px;
        margin-bottom: 8px; color: #3fb950; font-size: 14px;
    }
    .strength-card::before { content: "✓ "; font-weight: 700; }

    .gap-card {
        background: #3d0c0c; border: 1px solid #da3633;
        border-radius: 10px; padding: 12px 14px;
        margin-bottom: 8px; color: #f85149; font-size: 14px;
    }
    .gap-card::before { content: "△ "; font-weight: 700; }

    .next-step {
        background: #161b22; border: 1px solid #30363d;
        border-radius: 10px; padding: 12px 14px;
        margin-bottom: 8px; color: #c9d1d9; font-size: 14px;
        counter-increment: steps;
    }

    /* ── Section headings ──────────────────────────────────────────── */
    .section-title {
        font-size: 16px; font-weight: 600; color: #e6edf3;
        margin: 20px 0 10px; padding-bottom: 6px;
        border-bottom: 1px solid #21262d;
    }

    /* ── Reset button ──────────────────────────────────────────────── */
    div[data-testid="stButton"] > button:first-child {
        background: linear-gradient(135deg, #1f6feb, #58a6ff);
        color: white; border: none; border-radius: 8px;
        font-weight: 600; width: 100%; padding: 10px;
        transition: opacity 0.2s;
    }
    div[data-testid="stButton"] > button:first-child:hover { opacity: 0.85; }

    /* ── Hide Streamlit chrome ─────────────────────────────────────── */
    #MainMenu, footer, header { visibility: hidden; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ──────────────────────────────────────────────────────────────────────────────
# Data helpers
# ──────────────────────────────────────────────────────────────────────────────

_DATA_PATH = Path(__file__).resolve().parent / "data" / "candidate.json"


@st.cache_data(show_spinner=False)
def load_candidates() -> List[Dict[str, Any]]:
    """Load and return the list of all candidates from the local JSON file."""
    with open(_DATA_PATH, "r", encoding="utf-8") as fh:
        return json.load(fh)["candidates"]


def candidate_label(cand: Dict[str, Any]) -> str:
    m = cand["member"]
    return f"{m['name']} — {m['jobRole']}"


def first_try_rate(signals: Dict[str, Any]) -> int:
    completed = signals.get("missionsCompleted", 0)
    first_try = signals.get("missionsFirstTry", 0)
    return round((first_try / completed) * 100) if completed else 0


# ──────────────────────────────────────────────────────────────────────────────
# Session state initialisation
# ──────────────────────────────────────────────────────────────────────────────

def _init_session() -> None:
    """Ensure all required keys exist in st.session_state."""
    defaults = {
        "session_id": str(uuid.uuid4()),
        "messages": [],          # list of {"role": "user"|"assistant", "content": str}
        "interview_started": False,
        "feedback": None,        # populated when backend returns a feedback object
        "selected_idx": 0,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def reset_session() -> None:
    """Clear chat state and generate a fresh session ID."""
    st.session_state.session_id = str(uuid.uuid4())
    st.session_state.messages = []
    st.session_state.interview_started = False
    st.session_state.feedback = None


# ──────────────────────────────────────────────────────────────────────────────
# API call helper
# ──────────────────────────────────────────────────────────────────────────────

def call_interview_api(
    base_url: str,
    session_id: str,
    candidate: Optional[Dict[str, Any]] = None,
    message: Optional[str] = None,
    timeout: int = 45,
) -> Dict[str, Any]:
    """
    POST /api/interview — wraps both first-turn (with candidate) and
    subsequent turns (with message only).

    Raises requests.RequestException on any network/HTTP failure.
    """
    payload: Dict[str, Any] = {"sessionId": session_id}
    if candidate:
        payload["candidate"] = candidate
    if message:
        payload["message"] = message

    resp = requests.post(
        f"{base_url.rstrip('/')}/api/interview",
        json=payload,
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json()


# ──────────────────────────────────────────────────────────────────────────────
# Feedback Markdown export generator
# ──────────────────────────────────────────────────────────────────────────────

def build_markdown_report(
    candidate: Dict[str, Any],
    feedback: Dict[str, Any],
) -> str:
    member   = candidate["member"]
    signals  = candidate.get("signals", {})
    now      = datetime.now().strftime("%B %d, %Y · %H:%M")

    strengths = "\n".join(f"- ✓ {s}" for s in feedback.get("strengths", []))
    gaps      = "\n".join(f"- △ {g}" for g in feedback.get("gaps", []))
    next_steps = "\n".join(
        f"{i + 1}. {n}" for i, n in enumerate(feedback.get("next", []))
    )

    return f"""# Technical Readiness Assessment
> **Generated by AI Cohort Interview Agent · {now}**

---

## Candidate Profile

| Field              | Value                             |
|--------------------|-----------------------------------|
| **Name**           | {member['name']}                  |
| **Role**           | {member['jobRole']}               |
| **Experience**     | {member['yearsExperience']} years |
| **Education**      | {member['education']}             |
| **Cohort Status**  | {member['status']}                |
| **Commit Days**    | {signals.get('commitDays', '—')}/31 |
| **Missions Done**  | {signals.get('missionsCompleted', '—')} |
| **First-Try Rate** | {first_try_rate(signals)}%        |

---

## Executive Summary

{feedback.get('summary', 'No summary available.')}

---

## Strengths

{strengths if strengths else "None recorded."}

---

## Identified Gaps

{gaps if gaps else "None recorded."}

---

## Actionable Next Steps

{next_steps if next_steps else "None recorded."}

---

*This evaluation was generated automatically by the AI Cohort Interview Agent.
Results should be reviewed by a senior technical hiring manager before making
final placement decisions.*
"""


# ──────────────────────────────────────────────────────────────────────────────
# UI Components
# ──────────────────────────────────────────────────────────────────────────────

def render_bio_card(candidate: Dict[str, Any]) -> None:
    member  = candidate["member"]
    signals = candidate.get("signals", {})
    rate    = first_try_rate(signals)

    status_cls = "badge-green" if member["status"] == "COMPLETED" else "badge-blue"

    st.markdown(
        f"""
        <div class="bio-card">
            <div class="bio-title">{member['name']}</div>
            <div class="bio-sub">{member['jobRole']}</div>
            <div class="bio-row">
                <span class="bio-badge">{member['yearsExperience']} yrs exp</span>
                <span class="bio-badge">{member['education']}</span>
                <span class="bio-badge {status_cls}">{member['status']}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        f"""
        <div class="kpi-grid">
            <div class="kpi-card">
                <div class="kpi-val">{signals.get('commitDays', '—')}</div>
                <div class="kpi-lbl">Commit Days</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-val">{signals.get('missionsCompleted', '—')}</div>
                <div class="kpi-lbl">Missions Done</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-val">{rate}%</div>
                <div class="kpi-lbl">First-Try Rate</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_mission_timeline(candidate: Dict[str, Any]) -> None:
    """Render coloured mission pills across the top of the main area."""
    st.markdown('<p class="section-title">📅 Curriculum Journey & Competency Map</p>', unsafe_allow_html=True)

    pills_html = '<div class="mission-grid">'
    for mission in candidate.get("missions", []):
        day   = mission.get("day", "?")
        title = mission.get("title", f"Day {day}")
        short = title[:22] + "…" if len(title) > 24 else title

        if mission.get("passed"):
            attempts = mission.get("attempts", 1)
            label    = f"✓ Day {day}: {short} [{attempts}×]"
            cls      = "pill-pass"
        elif mission.get("skipped"):
            label = f"◌ Day {day}: {short} [Skipped]"
            cls   = "pill-skip"
        else:
            attempts = mission.get("attempts", "?")
            label    = f"✗ Day {day}: {short} [{attempts}×]"
            cls      = "pill-fail"

        pills_html += f'<span class="mission-pill {cls}" title="{title}">{label}</span>'

    pills_html += "</div>"
    st.markdown(pills_html, unsafe_allow_html=True)


def render_feedback_panel(feedback: Dict[str, Any], candidate: Dict[str, Any]) -> None:
    """Render the full Technical Readiness Assessment panel."""
    member = candidate["member"]

    st.markdown(
        f"""
        <div class="panel-header">
            <p class="panel-title">🏆 Technical Readiness Assessment</p>
            <p class="panel-sub">{member['name']} · {member['jobRole']} · Evaluated {datetime.now().strftime("%B %d, %Y")}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Executive Summary
    st.markdown('<p class="section-title">📋 Executive Summary</p>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="summary-box">{feedback.get("summary", "No summary available.")}</div>',
        unsafe_allow_html=True,
    )

    # Strengths & Gaps — two columns
    col_l, col_r = st.columns(2)

    with col_l:
        st.markdown('<p class="section-title">💪 Identified Strengths</p>', unsafe_allow_html=True)
        strengths = feedback.get("strengths", [])
        if strengths:
            for s in strengths:
                st.markdown(f'<div class="strength-card">{s}</div>', unsafe_allow_html=True)
        else:
            st.info("No strengths recorded.")

    with col_r:
        st.markdown('<p class="section-title">⚠️ Identified Gaps</p>', unsafe_allow_html=True)
        gaps = feedback.get("gaps", [])
        if gaps:
            for g in gaps:
                st.markdown(f'<div class="gap-card">{g}</div>', unsafe_allow_html=True)
        else:
            st.success("No significant gaps identified.")

    # Next steps
    st.markdown('<p class="section-title">🗺️ Actionable Learning Roadmap</p>', unsafe_allow_html=True)
    next_steps = feedback.get("next", [])
    for i, step in enumerate(next_steps, 1):
        st.markdown(
            f'<div class="next-step"><strong>Step {i}:</strong> {step}</div>',
            unsafe_allow_html=True,
        )

    # Download report
    st.markdown("---")
    report_md = build_markdown_report(candidate, feedback)
    st.download_button(
        label="⬇️  Download Evaluation Report (.md)",
        data=report_md,
        file_name=f"evaluation_{member['id']}_{datetime.now().strftime('%Y%m%d_%H%M')}.md",
        mime="text/markdown",
        use_container_width=True,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Main application
# ──────────────────────────────────────────────────────────────────────────────

def main() -> None:
    _init_session()

    candidates = load_candidates()

    # ── SIDEBAR ────────────────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown(
            "<h1 style='color:#58a6ff;font-size:22px;margin-bottom:0'>🤖 AI Interview Agent</h1>"
            "<p style='color:#8b949e;font-size:13px;margin-top:4px'>Powered by Groq Llama-3</p>",
            unsafe_allow_html=True,
        )
        st.divider()

        # API URL config
        st.markdown("**🌐 Backend API URL**")
        api_url = st.text_input(
            "API URL",
            value="http://localhost:8000",
            label_visibility="collapsed",
            key="api_url",
        )
        st.caption("Use `https://ai-cohort-seven.vercel.app` for the deployed version.")
        st.divider()

        # Candidate selector
        st.markdown("**👤 Candidate Profile**")
        candidate_labels = [candidate_label(c) for c in candidates]
        selected_idx = st.selectbox(
            "Select Candidate",
            options=range(len(candidates)),
            format_func=lambda i: candidate_labels[i],
            key="selected_idx",
            label_visibility="collapsed",
        )
        selected_candidate = candidates[selected_idx]

        # Bio card + KPIs
        render_bio_card(selected_candidate)
        st.divider()

        # Reset / Start
        if st.button("🔄  Reset & Start New Interview", use_container_width=True):
            reset_session()
            st.rerun()

        if st.session_state.interview_started:
            st.caption(f"Session: `{st.session_state.session_id[:8]}…`")

    # ── MAIN AREA ──────────────────────────────────────────────────────────────
    st.markdown(
        "<h2 style='color:#e6edf3;margin-bottom:4px'>AI Cohort · Technical Interview Simulator</h2>"
        "<p style='color:#8b949e;margin-bottom:20px'>Select a candidate, then start the interview. "
        "The agent adapts its questions to their exact curriculum journey.</p>",
        unsafe_allow_html=True,
    )

    # Competency map
    render_mission_timeline(selected_candidate)
    st.divider()

    # ── CHAT SECTION ──────────────────────────────────────────────────────────

    # If feedback has been returned, show the panel instead of the chat input
    if st.session_state.feedback:
        # Replay conversation in collapsed expander
        with st.expander("💬 View Full Conversation Transcript", expanded=False):
            for msg in st.session_state.messages:
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])

        render_feedback_panel(st.session_state.feedback, selected_candidate)
        return  # Don't render chat input after interview is done

    # Replay stored conversation history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Chat input — only shown when interview is not complete
    chat_placeholder = (
        "Click here to start the interview →  type anything or just press Enter"
        if not st.session_state.interview_started
        else "Type your answer and press Enter…"
    )

    user_input = st.chat_input(chat_placeholder)

    if user_input is not None:
        # Determine if this is the very first turn
        is_first_turn = not st.session_state.interview_started

        # Echo user message immediately (skip echo on first turn — it's just "start")
        if not is_first_turn:
            st.session_state.messages.append({"role": "user", "content": user_input})
            with st.chat_message("user"):
                st.markdown(user_input)

        # Call backend
        with st.spinner("Interviewer is evaluating your response…"):
            try:
                if is_first_turn:
                    # First call: send full candidate payload, no message
                    result = call_interview_api(
                        base_url=api_url,
                        session_id=st.session_state.session_id,
                        candidate=selected_candidate,
                        message=None,
                    )
                    st.session_state.interview_started = True
                else:
                    # Subsequent calls: send message only
                    result = call_interview_api(
                        base_url=api_url,
                        session_id=st.session_state.session_id,
                        candidate=None,
                        message=user_input,
                    )

                agent_msg = result.get("message", "")
                feedback  = result.get("feedback")

                # Store and display agent response
                if agent_msg:
                    st.session_state.messages.append({"role": "assistant", "content": agent_msg})
                    with st.chat_message("assistant"):
                        st.markdown(agent_msg)

                # If feedback was returned, store it and rerun to show the panel
                if feedback:
                    st.session_state.feedback = feedback
                    st.rerun()

            except requests.exceptions.ConnectionError:
                st.warning(
                    "⚠️ **Connection Error** — Could not reach the backend API. "
                    "Please check the API URL in the sidebar and ensure the server is running."
                )
            except requests.exceptions.Timeout:
                st.warning(
                    "⏱️ **Timeout** — The backend took too long to respond. "
                    "Groq/Vercel cold starts can take up to 30s — please try again."
                )
            except requests.exceptions.HTTPError as exc:
                try:
                    detail = exc.response.json().get("detail", str(exc))
                except Exception:
                    detail = str(exc)
                st.error(f"❌ **API Error ({exc.response.status_code}):** {detail}")
            except Exception as exc:
                st.error(f"❌ **Unexpected error:** {exc}")


if __name__ == "__main__":
    main()
