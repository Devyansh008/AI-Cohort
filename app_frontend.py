"""
app_frontend.py

Premium Glassmorphism Streamlit dashboard for the AI Cohort Interview Agent.

Features:
  - Deep dark animated background with glassmorphism card components
  - Zero-click auto-greeting: interview starts automatically on candidate select/reset
  - Judge Assist: 3 one-click simulated answer buttons for live demo
  - Curriculum Competency Map with neon-glow mission badges
  - Technical Readiness Assessment panel with Markdown export on completion

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
# Page config — MUST be first Streamlit call
# ──────────────────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="AI Cohort · Interview Agent",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ──────────────────────────────────────────────────────────────────────────────
# Glassmorphism CSS
# ──────────────────────────────────────────────────────────────────────────────

st.markdown("""
<style>
/* ── Fonts ───────────────────────────────────────────────────────────────── */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
*, html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

/* ── Animated gradient background ───────────────────────────────────────── */
.stApp {
    background: linear-gradient(135deg, #0a0e1a 0%, #0d1117 30%, #0f0c29 60%, #090d1f 100%);
    min-height: 100vh;
}
.stApp::before {
    content: '';
    position: fixed;
    top: -50%;
    left: -50%;
    width: 200%;
    height: 200%;
    background: radial-gradient(ellipse at 20% 50%, rgba(120,40,200,0.08) 0%, transparent 50%),
                radial-gradient(ellipse at 80% 20%, rgba(0,100,255,0.07) 0%, transparent 50%),
                radial-gradient(ellipse at 60% 80%, rgba(0,200,150,0.05) 0%, transparent 50%);
    pointer-events: none;
    z-index: 0;
}

/* ── Sidebar ─────────────────────────────────────────────────────────────── */
section[data-testid="stSidebar"] {
    background: rgba(10, 14, 26, 0.92) !important;
    border-right: 1px solid rgba(255,255,255,0.07) !important;
    backdrop-filter: blur(20px);
}
section[data-testid="stSidebar"] * { color: #e2e8f0 !important; }
section[data-testid="stSidebar"] .stTextInput input {
    background: rgba(255,255,255,0.05) !important;
    border: 1px solid rgba(255,255,255,0.1) !important;
    color: #e2e8f0 !important;
    border-radius: 8px !important;
}
section[data-testid="stSidebar"] .stSelectbox > div > div {
    background: rgba(255,255,255,0.05) !important;
    border: 1px solid rgba(255,255,255,0.1) !important;
    border-radius: 8px !important;
}

/* ── Glass card base ─────────────────────────────────────────────────────── */
.glass-card {
    background: rgba(17, 25, 40, 0.75);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border: 1px solid rgba(255, 255, 255, 0.125);
    border-radius: 16px;
    padding: 20px 22px;
    margin-bottom: 16px;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4),
                inset 0 1px 0 rgba(255,255,255,0.08);
    position: relative;
    overflow: hidden;
}
.glass-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 1px;
    background: linear-gradient(90deg, transparent, rgba(255,255,255,0.15), transparent);
}

/* ── Bio card ────────────────────────────────────────────────────────────── */
.bio-name {
    font-size: 18px;
    font-weight: 700;
    color: #f0f6ff;
    margin: 0 0 2px;
    letter-spacing: -0.3px;
}
.bio-role {
    font-size: 13px;
    color: rgba(148,163,184,0.9);
    margin-bottom: 12px;
}
.badge-row { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 10px; }
.badge {
    font-size: 11px; font-weight: 500;
    padding: 3px 10px; border-radius: 20px;
    border: 1px solid;
    white-space: nowrap;
}
.badge-default {
    background: rgba(255,255,255,0.06);
    border-color: rgba(255,255,255,0.12);
    color: #94a3b8;
}
.badge-green {
    background: rgba(16,185,129,0.15);
    border-color: rgba(16,185,129,0.4);
    color: #10b981;
}
.badge-blue {
    background: rgba(59,130,246,0.15);
    border-color: rgba(59,130,246,0.4);
    color: #60a5fa;
}

/* ── KPI grid ────────────────────────────────────────────────────────────── */
.kpi-grid { display: grid; grid-template-columns: repeat(3,1fr); gap: 8px; margin-top: 8px; }
.kpi-card {
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 12px;
    padding: 12px 6px;
    text-align: center;
}
.kpi-val {
    font-size: 22px; font-weight: 800;
    background: linear-gradient(135deg, #60a5fa, #a78bfa);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    background-clip: text;
}
.kpi-lbl { font-size: 10px; color: rgba(148,163,184,0.7); margin-top: 2px; letter-spacing: 0.3px; }

/* ── Section heading ─────────────────────────────────────────────────────── */
.section-heading {
    font-size: 13px; font-weight: 600; letter-spacing: 0.8px; text-transform: uppercase;
    color: rgba(148,163,184,0.7);
    margin: 0 0 12px;
    padding-bottom: 8px;
    border-bottom: 1px solid rgba(255,255,255,0.06);
}

/* ── Mission pills (competency map) ─────────────────────────────────────── */
.mission-grid { display: flex; flex-wrap: wrap; gap: 7px; }
.mpill {
    font-size: 11.5px; font-weight: 500;
    padding: 5px 12px; border-radius: 20px;
    border: 1px solid;
    white-space: nowrap;
    transition: transform 0.15s, box-shadow 0.15s;
    cursor: default;
}
.mpill:hover { transform: translateY(-1px); }
.mpill-pass {
    background: rgba(16,185,129,0.12);
    border-color: rgba(16,185,129,0.35);
    color: #34d399;
    box-shadow: 0 0 10px rgba(16,185,129,0.12);
}
.mpill-skip {
    background: rgba(255,255,255,0.05);
    border-color: rgba(148,163,184,0.2);
    color: rgba(148,163,184,0.7);
}
.mpill-fail {
    background: rgba(239,68,68,0.12);
    border-color: rgba(239,68,68,0.35);
    color: #f87171;
    box-shadow: 0 0 10px rgba(239,68,68,0.1);
}

/* ── Page title ──────────────────────────────────────────────────────────── */
.page-title {
    font-size: 32px; font-weight: 800; letter-spacing: -1px;
    background: linear-gradient(135deg, #f0f6ff 0%, #a78bfa 50%, #60a5fa 100%);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    background-clip: text;
    margin: 0 0 4px;
}
.page-sub { font-size: 14px; color: rgba(148,163,184,0.7); margin-bottom: 24px; }

/* ── Divider ─────────────────────────────────────────────────────────────── */
.glass-divider {
    height: 1px;
    background: linear-gradient(90deg, transparent, rgba(255,255,255,0.1), transparent);
    margin: 20px 0;
}

/* ── Feedback panel ──────────────────────────────────────────────────────── */
.panel-header {
    background: linear-gradient(135deg, rgba(30,58,138,0.6), rgba(5,46,22,0.6));
    border-radius: 16px 16px 0 0;
    padding: 22px 28px;
    border: 1px solid rgba(255,255,255,0.1);
    border-bottom: none;
}
.panel-title { font-size: 22px; font-weight: 700; color: #f0f6ff; margin: 0 0 4px; }
.panel-sub { font-size: 13px; color: rgba(148,163,184,0.7); margin: 0; }
.summary-box {
    background: rgba(17,25,40,0.7);
    border-left: 3px solid #60a5fa;
    border-radius: 0 10px 10px 0;
    padding: 16px 20px;
    margin: 16px 0;
    color: rgba(226,232,240,0.9);
    line-height: 1.75;
    font-size: 14px;
}
.strength-card {
    background: rgba(16,185,129,0.08);
    border: 1px solid rgba(16,185,129,0.25);
    border-radius: 10px; padding: 12px 14px;
    margin-bottom: 8px; color: #6ee7b7; font-size: 13.5px;
    line-height: 1.5;
}
.strength-card::before { content: "✓  "; font-weight: 700; }
.gap-card {
    background: rgba(239,68,68,0.08);
    border: 1px solid rgba(239,68,68,0.25);
    border-radius: 10px; padding: 12px 14px;
    margin-bottom: 8px; color: #fca5a5; font-size: 13.5px;
    line-height: 1.5;
}
.gap-card::before { content: "△  "; font-weight: 700; }
.next-step {
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 10px; padding: 12px 14px;
    margin-bottom: 8px; color: #e2e8f0; font-size: 13.5px;
    line-height: 1.5;
}

/* ── Judge assist buttons ────────────────────────────────────────────────── */
.judge-row { display: flex; gap: 10px; flex-wrap: wrap; margin: 12px 0 0; }

/* ── Reset button ────────────────────────────────────────────────────────── */
div[data-testid="stButton"] > button {
    background: linear-gradient(135deg, #1e40af, #7c3aed) !important;
    color: #fff !important; border: none !important;
    border-radius: 10px !important; font-weight: 600 !important;
    width: 100% !important; padding: 10px !important;
    transition: opacity 0.2s, transform 0.1s !important;
    letter-spacing: 0.2px !important;
}
div[data-testid="stButton"] > button:hover {
    opacity: 0.88 !important; transform: translateY(-1px) !important;
}

/* ── Chat messages ───────────────────────────────────────────────────────── */
[data-testid="stChatMessage"] {
    background: rgba(17,25,40,0.6) !important;
    border: 1px solid rgba(255,255,255,0.07) !important;
    border-radius: 14px !important;
    backdrop-filter: blur(8px) !important;
    margin-bottom: 8px !important;
}

/* ── Chat input ──────────────────────────────────────────────────────────── */
[data-testid="stChatInput"] textarea {
    background: rgba(17,25,40,0.8) !important;
    border: 1px solid rgba(255,255,255,0.1) !important;
    border-radius: 12px !important;
    color: #e2e8f0 !important;
}

/* ── Hide Streamlit chrome ───────────────────────────────────────────────── */
#MainMenu, footer, header { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────────────

_DATA_PATH = Path(__file__).resolve().parent / "data" / "candidate.json"
_API_DEFAULT = "https://ai-cohort-seven.vercel.app"

_STRONG_ANSWER = (
    "I used Sentence Transformers with a ChromaDB backend, choosing 384-dimensional "
    "embeddings to optimise matching speed while preserving 94% semantic resolution "
    "verified by PCA cluster plots. I evaluated cosine similarity vs. dot-product "
    "and settled on cosine for normalised vectors."
)
_WEAK_ANSWER = (
    "I just used a standard open-source library, loaded the data, and created some "
    "basic plots to visualise it. It seemed to work fine for the project."
)
_SKIP_ANSWER = (
    "I actually skipped that monitoring module during the cohort, but I understand "
    "the theory behind distributed logging and observability in LLM pipelines."
)

# ──────────────────────────────────────────────────────────────────────────────
# Data helpers
# ──────────────────────────────────────────────────────────────────────────────

@st.cache_data(show_spinner=False)
def load_candidates() -> List[Dict[str, Any]]:
    with open(_DATA_PATH, "r", encoding="utf-8") as fh:
        return json.load(fh)["candidates"]


def candidate_label(c: Dict[str, Any]) -> str:
    m = c["member"]
    return f"{m['name']} — {m['jobRole']}"


def first_try_rate(signals: Dict[str, Any]) -> int:
    c = signals.get("missionsCompleted", 0)
    f = signals.get("missionsFirstTry", 0)
    return round((f / c) * 100) if c else 0


# ──────────────────────────────────────────────────────────────────────────────
# API
# ──────────────────────────────────────────────────────────────────────────────

def call_api(
    base_url: str,
    session_id: str,
    candidate: Optional[Dict] = None,
    message: Optional[str] = None,
    timeout: int = 55,
) -> Dict[str, Any]:
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
# Session state
# ──────────────────────────────────────────────────────────────────────────────

def _defaults() -> Dict[str, Any]:
    return {
        "session_id": str(uuid.uuid4()),
        "messages": [],
        "feedback": None,
        "auto_started": False,       # True once the auto-greeting has fired
        "pending_sim": None,         # Queued simulated answer text
        "last_candidate_idx": None,  # Detect candidate switch
    }


def _init() -> None:
    for k, v in _defaults().items():
        if k not in st.session_state:
            st.session_state[k] = v


def reset(new_candidate_idx: Optional[int] = None) -> None:
    """Full session reset, optionally switching candidate."""
    for k, v in _defaults().items():
        st.session_state[k] = v
    if new_candidate_idx is not None:
        st.session_state.last_candidate_idx = new_candidate_idx


# ──────────────────────────────────────────────────────────────────────────────
# Markdown export
# ──────────────────────────────────────────────────────────────────────────────

def build_report(candidate: Dict, feedback: Dict) -> str:
    m = candidate["member"]
    sig = candidate.get("signals", {})
    now = datetime.now().strftime("%B %d, %Y · %H:%M")
    strengths = "\n".join(f"- ✓ {s}" for s in feedback.get("strengths", []))
    gaps      = "\n".join(f"- △ {g}" for g in feedback.get("gaps", []))
    steps     = "\n".join(f"{i+1}. {n}" for i, n in enumerate(feedback.get("next", [])))
    return f"""# Technical Readiness Assessment
> **Generated by AI Cohort Interview Agent · {now}**

---

## Candidate Profile

| Field | Value |
|---|---|
| **Name** | {m['name']} |
| **Role** | {m['jobRole']} |
| **Experience** | {m['yearsExperience']} years |
| **Education** | {m['education']} |
| **Cohort Status** | {m['status']} |
| **Commit Days** | {sig.get('commitDays','—')}/31 |
| **Missions Done** | {sig.get('missionsCompleted','—')} |
| **First-Try Rate** | {first_try_rate(sig)}% |

---

## Executive Summary

{feedback.get('summary','No summary available.')}

---

## Strengths

{strengths or 'None recorded.'}

---

## Identified Gaps

{gaps or 'None recorded.'}

---

## Actionable Next Steps

{steps or 'None recorded.'}

---
*Evaluated automatically by the AI Cohort Interview Agent.*
"""


# ──────────────────────────────────────────────────────────────────────────────
# UI component renderers
# ──────────────────────────────────────────────────────────────────────────────

def render_bio_card(candidate: Dict) -> None:
    m   = candidate["member"]
    sig = candidate.get("signals", {})
    rate = first_try_rate(sig)
    status_cls = "badge-green" if m["status"] == "COMPLETED" else "badge-blue"

    st.markdown(f"""
    <div class="glass-card">
        <div class="bio-name">{m['name']}</div>
        <div class="bio-role">{m['jobRole']}</div>
        <div class="badge-row">
            <span class="badge badge-default">{m['yearsExperience']} yrs</span>
            <span class="badge badge-default">{m['education']}</span>
            <span class="badge {status_cls}">{m['status']}</span>
        </div>
        <div class="kpi-grid">
            <div class="kpi-card">
                <div class="kpi-val">{sig.get('commitDays','—')}</div>
                <div class="kpi-lbl">Commit Days</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-val">{sig.get('missionsCompleted','—')}</div>
                <div class="kpi-lbl">Missions</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-val">{rate}%</div>
                <div class="kpi-lbl">1st-Try Rate</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_competency_map(candidate: Dict) -> None:
    st.markdown('<p class="section-heading">📅 Curriculum Competency Map</p>', unsafe_allow_html=True)
    pills = ""
    for m in candidate.get("missions", []):
        day   = m.get("day", "?")
        title = m.get("title", f"Day {day}")
        short = (title[:20] + "…") if len(title) > 22 else title
        if m.get("passed"):
            cls   = "mpill-pass"
            label = f"✓ Day {day}: {short} [{m.get('attempts',1)}×]"
        elif m.get("skipped"):
            cls   = "mpill-skip"
            label = f"◌ Day {day}: {short} [Skipped]"
        else:
            cls   = "mpill-fail"
            label = f"✗ Day {day}: {short} [{m.get('attempts','?')}×]"
        pills += f'<span class="mpill {cls}" title="{title}">{label}</span>'
    st.markdown(f'<div class="mission-grid">{pills}</div>', unsafe_allow_html=True)


def render_feedback_panel(feedback: Dict, candidate: Dict) -> None:
    m = candidate["member"]
    st.markdown(f"""
    <div class="panel-header">
        <p class="panel-title">🏆 Technical Readiness Assessment</p>
        <p class="panel-sub">{m['name']} · {m['jobRole']} · {datetime.now().strftime("%B %d, %Y")}</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<p class="section-heading" style="margin-top:20px">📋 Executive Summary</p>', unsafe_allow_html=True)
    st.markdown(f'<div class="summary-box">{feedback.get("summary","")}</div>', unsafe_allow_html=True)

    col_l, col_r = st.columns(2)
    with col_l:
        st.markdown('<p class="section-heading">💪 Strengths</p>', unsafe_allow_html=True)
        for s in feedback.get("strengths", []):
            st.markdown(f'<div class="strength-card">{s}</div>', unsafe_allow_html=True)
    with col_r:
        st.markdown('<p class="section-heading">⚠️ Identified Gaps</p>', unsafe_allow_html=True)
        for g in feedback.get("gaps", []):
            st.markdown(f'<div class="gap-card">{g}</div>', unsafe_allow_html=True)

    st.markdown('<p class="section-heading" style="margin-top:16px">🗺️ Learning Roadmap</p>', unsafe_allow_html=True)
    for i, step in enumerate(feedback.get("next", []), 1):
        st.markdown(f'<div class="next-step"><strong>Step {i}:</strong> {step}</div>', unsafe_allow_html=True)

    st.markdown('<div class="glass-divider"></div>', unsafe_allow_html=True)
    st.download_button(
        label="⬇️  Download Evaluation Report (.md)",
        data=build_report(candidate, feedback),
        file_name=f"eval_{m['id']}_{datetime.now().strftime('%Y%m%d_%H%M')}.md",
        mime="text/markdown",
        use_container_width=True,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Auto-greeting helper
# ──────────────────────────────────────────────────────────────────────────────

def auto_start_interview(api_url: str, candidate: Dict) -> None:
    """Fire the first-turn API call and store the greeting in session state."""
    with st.spinner("🤖 Initialising interview…"):
        try:
            result = call_api(
                base_url=api_url,
                session_id=st.session_state.session_id,
                candidate=candidate,
            )
            msg      = result.get("message", "")
            feedback = result.get("feedback")
            if msg:
                st.session_state.messages.append({"role": "assistant", "content": msg})
            if feedback:
                st.session_state.feedback = feedback
        except Exception as exc:
            st.session_state.messages.append({
                "role": "assistant",
                "content": f"⚠️ Could not reach the backend ({exc}). Check the API URL in the sidebar.",
            })
    st.session_state.auto_started = True


# ──────────────────────────────────────────────────────────────────────────────
# Main application
# ──────────────────────────────────────────────────────────────────────────────

def main() -> None:
    _init()
    candidates = load_candidates()

    # ── SIDEBAR ───────────────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown(
            "<h1 style='font-size:20px;font-weight:800;color:#f0f6ff;margin:0'>🤖 AI Interview Agent</h1>"
            "<p style='font-size:12px;color:rgba(148,163,184,0.7);margin:2px 0 16px'>Powered by Groq Llama-3.3</p>",
            unsafe_allow_html=True,
        )
        st.divider()

        # API URL
        st.markdown("**🌐 Backend API**")
        api_url = st.text_input(
            "API URL",
            value=_API_DEFAULT,
            label_visibility="collapsed",
            key="api_url",
        )
        st.caption("Change to `http://localhost:8000` for local dev.")
        st.divider()

        # Candidate selector
        st.markdown("**👤 Select Candidate**")
        candidate_idx = st.selectbox(
            "Candidate",
            options=range(len(candidates)),
            format_func=lambda i: candidate_label(candidates[i]),
            label_visibility="collapsed",
            key="candidate_idx",
        )
        selected = candidates[candidate_idx]

        # Detect candidate switch → auto-reset
        if st.session_state.last_candidate_idx != candidate_idx:
            reset(new_candidate_idx=candidate_idx)
            st.rerun()

        # Bio card + KPIs
        render_bio_card(selected)
        st.divider()

        # Reset button
        if st.button("🔄  Reset & Start New Interview", use_container_width=True):
            reset(new_candidate_idx=candidate_idx)
            st.rerun()

        if st.session_state.auto_started:
            st.caption(f"Session: `{st.session_state.session_id[:8]}…`")

    # ── MAIN PAGE ─────────────────────────────────────────────────────────────
    st.markdown(
        '<p class="page-title">AI Cohort · Interview Simulator</p>'
        '<p class="page-sub">Adaptive technical interviews driven by each candidate\'s exact learning journey.</p>',
        unsafe_allow_html=True,
    )

    # Competency map
    render_competency_map(selected)
    st.markdown('<div class="glass-divider"></div>', unsafe_allow_html=True)

    # ── AUTO-GREETING ─────────────────────────────────────────────────────────
    # Fire automatically if the session hasn't started yet
    if not st.session_state.auto_started:
        auto_start_interview(api_url, selected)
        st.rerun()

    # ── If interview is complete, show feedback panel ─────────────────────────
    if st.session_state.feedback:
        with st.expander("💬 Full Conversation Transcript", expanded=False):
            for msg in st.session_state.messages:
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])
        render_feedback_panel(st.session_state.feedback, selected)
        return

    # ── Chat replay ───────────────────────────────────────────────────────────
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # ── Judge Assist buttons ──────────────────────────────────────────────────
    st.markdown('<div class="glass-divider"></div>', unsafe_allow_html=True)
    st.markdown(
        "<p style='font-size:12px;font-weight:600;letter-spacing:0.6px;"
        "text-transform:uppercase;color:rgba(148,163,184,0.6);margin:0 0 8px'>⚡ Judge Assist — Simulated Answers</p>",
        unsafe_allow_html=True,
    )
    col1, col2, col3 = st.columns(3)
    sim_text: Optional[str] = None

    with col1:
        if st.button("🟢  Strong Answer", use_container_width=True, key="btn_strong"):
            sim_text = _STRONG_ANSWER
    with col2:
        if st.button("🟡  Vague Answer", use_container_width=True, key="btn_weak"):
            sim_text = _WEAK_ANSWER
    with col3:
        if st.button("🔴  Gap / Skip", use_container_width=True, key="btn_skip"):
            sim_text = _SKIP_ANSWER

    # If a sim button was clicked, queue the text
    if sim_text:
        st.session_state.pending_sim = sim_text
        st.rerun()

    # ── Manual chat input ─────────────────────────────────────────────────────
    user_input = st.chat_input("Type your answer or press one of the Judge Assist buttons above…")

    # Resolve which text to send (pending_sim takes priority over typed input)
    text_to_send: Optional[str] = None
    if st.session_state.pending_sim:
        text_to_send = st.session_state.pending_sim
        st.session_state.pending_sim = None
    elif user_input:
        text_to_send = user_input

    if text_to_send:
        # Display user bubble immediately
        st.session_state.messages.append({"role": "user", "content": text_to_send})
        with st.chat_message("user"):
            st.markdown(text_to_send)

        # Call backend
        with st.spinner("🤖 Interviewer is evaluating your response…"):
            try:
                result = call_api(
                    base_url=api_url,
                    session_id=st.session_state.session_id,
                    message=text_to_send,
                )
                agent_msg = result.get("message", "")
                feedback  = result.get("feedback")

                if agent_msg:
                    st.session_state.messages.append({"role": "assistant", "content": agent_msg})
                    with st.chat_message("assistant"):
                        st.markdown(agent_msg)

                if feedback:
                    st.session_state.feedback = feedback
                    st.rerun()

            except requests.exceptions.ConnectionError:
                st.warning("⚠️ **Connection Error** — Cannot reach the backend. Check the API URL in the sidebar.")
            except requests.exceptions.Timeout:
                st.warning("⏱️ **Timeout** — The backend took too long (Vercel cold start can take ~30s). Please try again.")
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
