"""
app_frontend.py
World-class Streamlit frontend for the AI Cohort Interview Agent.
Upgraded with full Glassmorphism Dark Theme styling, Auto-Greeting,
and CONTEXT-AWARE One-Click Simulated Answers for instant grading.

Run: streamlit run app_frontend.py
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
# Global CSS – polished Glassmorphism Dark Theme
# ──────────────────────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    /* Dark Obsidian Background with subtle neon accent mesh */
    .stApp {
        background: radial-gradient(circle at 50% 10%, #161922 0%, #0F1015 100%);
        color: #E2E8F0;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }
    
    /* Top banner */
    .top-banner {
        text-align: center;
        padding: 1.5rem 0 2rem 0;
        border-bottom: 1px solid rgba(255, 255, 255, 0.05);
        margin-bottom: 2rem;
    }
    .top-title {
        font-size: 2.2rem;
        font-weight: 800;
        letter-spacing: -0.025em;
        background: linear-gradient(135deg, #60A5FA 0%, #A78BFA 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.2rem;
    }
    .top-subtitle {
        color: #94A3B8;
        font-size: 1rem;
        font-weight: 400;
    }

    /* Glassmorphism Sidebar */
    [data-testid="stSidebar"] {
        background: rgba(15, 16, 21, 0.85) !important;
        backdrop-filter: blur(20px);
        border-right: 1px solid rgba(255, 255, 255, 0.05);
    }
    
    .sidebar-title {
        font-size: 1.5rem;
        font-weight: 800;
        letter-spacing: -0.025em;
        background: linear-gradient(135deg, #60A5FA 0%, #34D399 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.5rem;
        text-align: center;
    }
    .sidebar-subtitle {
        color: #64748B;
        font-size: 0.8rem;
        text-align: center;
        margin-bottom: 1.5rem;
    }

    /* Glassmorphism Bio Card Container */
    .bio-card-container {
        background: rgba(255, 255, 255, 0.02);
        backdrop-filter: blur(12px);
        border: 1px solid rgba(255, 255, 255, 0.06);
        border-radius: 16px;
        padding: 1.25rem;
        margin-top: 1rem;
        box-shadow: 0 4px 30px rgba(0, 0, 0, 0.2);
    }
    
    .bio-name {
        font-size: 1.2rem;
        font-weight: 700;
        color: #FFFFFF;
        margin-bottom: 0.2rem;
    }
    .bio-role {
        font-size: 0.9rem;
        font-weight: 500;
        color: #60A5FA;
        margin-bottom: 0.75rem;
    }
    .bio-detail {
        font-size: 0.8rem;
        color: #94A3B8;
        margin-bottom: 0.4rem;
        display: flex;
        justify-content: space-between;
    }
    .bio-detail span {
        color: #F1F5F9;
        font-weight: 600;
    }
    
    /* Styled Status Badge in Sidebar */
    .status-badge {
        display: inline-block;
        font-size: 0.7rem;
        font-weight: 700;
        padding: 0.2rem 0.5rem;
        border-radius: 9999px;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-top: 0.5rem;
    }
    .badge-green {
        background: rgba(16, 185, 129, 0.15);
        color: #34D399;
        border: 1px solid rgba(16, 185, 129, 0.3);
    }
    .badge-blue {
        background: rgba(59, 130, 246, 0.15);
        color: #60A5FA;
        border: 1px solid rgba(59, 130, 246, 0.3);
    }

    /* Glassmorphic KPI Tiles */
    .kpi-wrapper {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 0.5rem;
        margin-top: 1rem;
    }
    .kpi-tile {
        background: rgba(255, 255, 255, 0.01);
        border: 1px solid rgba(255, 255, 255, 0.04);
        border-radius: 10px;
        padding: 0.5rem;
        text-align: center;
    }
    .kpi-value {
        font-size: 1.1rem;
        font-weight: 700;
        color: #FFFFFF;
    }
    .kpi-label {
        font-size: 0.65rem;
        color: #64748B;
        margin-top: 0.15rem;
        line-height: 1.1;
    }

    /* Curriculum Timeline Container */
    .timeline-container {
        background: rgba(255, 255, 255, 0.02);
        backdrop-filter: blur(12px);
        border: 1px solid rgba(255, 255, 255, 0.06);
        border-radius: 16px;
        padding: 1.25rem;
        margin-bottom: 2rem;
    }
    .timeline-title {
        font-size: 1rem;
        font-weight: 700;
        color: #F8FAFC;
        margin-bottom: 1rem;
        display: flex;
        align-items: center;
        gap: 0.5rem;
        border-bottom: 1px solid rgba(255, 255, 255, 0.05);
        padding-bottom: 0.5rem;
    }
    .timeline-grid {
        display: flex;
        flex-wrap: wrap;
        gap: 0.5rem;
    }

    /* Colored Timeline Badges */
    .pill-badge {
        font-size: 0.75rem;
        font-weight: 600;
        padding: 0.4rem 0.75rem;
        border-radius: 8px;
        display: inline-flex;
        align-items: center;
        gap: 0.3rem;
        transition: all 0.2s ease-in-out;
    }
    .pill-badge:hover {
        transform: translateY(-2px);
    }
    .pill-pass {
        background: rgba(16, 185, 129, 0.08);
        color: #34D399;
        border: 1px solid rgba(16, 185, 129, 0.2);
    }
    .pill-skip {
        background: rgba(245, 158, 11, 0.08);
        color: #FBBF24;
        border: 1px solid rgba(245, 158, 11, 0.2);
    }
    .pill-fail {
        background: rgba(239, 68, 68, 0.08);
        color: #FCA5A5;
        border: 1px solid rgba(239, 68, 68, 0.2);
    }

    /* Subsections Header styling */
    .section-header {
        font-size: 1.3rem;
        font-weight: 700;
        color: #FFFFFF;
        margin: 1.5rem 0 1rem 0;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }

    /* Custom Chat Styling & Cleanups */
    .stChatMessage {
        background: rgba(255, 255, 255, 0.02) !important;
        border: 1px solid rgba(255, 255, 255, 0.04) !important;
        border-radius: 12px !important;
        margin-bottom: 0.75rem !important;
    }
    
    /* Technical Readiness Report styling */
    .assessment-card {
        background: rgba(255, 255, 255, 0.03);
        backdrop-filter: blur(16px);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 16px;
        padding: 1.5rem;
        margin-top: 1.5rem;
        box-shadow: 0 10px 40px rgba(0, 0, 0, 0.3);
    }
    .assessment-header {
        font-size: 1.6rem;
        font-weight: 800;
        background: linear-gradient(135deg, #10B981 0%, #3B82F6 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 1.5rem;
        border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        padding-bottom: 0.75rem;
    }
    .assessment-block {
        background: rgba(255, 255, 255, 0.015);
        border: 1px solid rgba(255, 255, 255, 0.05);
        border-radius: 12px;
        padding: 1rem;
        margin-bottom: 1rem;
    }
    .assessment-block-title {
        font-size: 1rem;
        font-weight: 700;
        color: #F8FAFC;
        margin-bottom: 0.5rem;
    }
    
    .card-strengths {
        border-left: 4px solid #10B981;
    }
    .card-gaps {
        border-left: 4px solid #F59E0B;
    }
    .card-step {
        border-left: 4px solid #6366F1;
    }
    
    /* Simulated response header */
    .helper-header {
        font-size: 0.85rem;
        font-weight: 700;
        color: #94A3B8;
        margin-top: 1.5rem;
        margin-bottom: 0.5rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        display: flex;
        align-items: center;
        gap: 0.4rem;
    }
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
# Context-Aware Simulated Response Generator (Heuristic Fallback and Dynamic Parser)
# ──────────────────────────────────────────────────────────────────────────────
def get_dynamic_simulated_answers(last_question: str, candidate: Dict[str, Any]) -> Dict[str, str]:
    """
    Analyze the last question asked by the interviewer and return 3 context-specific answers:
    - strong: A high-quality, technically accurate response about the topic.
    - vague: A basic, superficial response.
    - gap: An honest admission of a gap or skipping the topic.
    """
    q = last_question.lower()
    name = candidate["member"]["name"]
    role = candidate["member"]["jobRole"]
    
    # Day 1 & 3: Environment, Setup, and React
    if any(k in q for k in ["day 1", "day 3", "environment", "setup", "vs code", "virtual environment", "vite", "react"]):
        return {
            "strong": "I set up a virtual environment (.venv) in VS Code, configuring Pylance for static type checking. I integrated a FastAPI backend with a React frontend built via Vite, publishing the complete repo to GitHub with clean committing patterns.",
            "vague": "I installed VS Code and Python, set up the backend and frontend folders, ran some npm commands, and pushed the files to my GitHub repository.",
            "gap": "Honestly, I had some trouble with the initial React setup, so my environment was a bit messy, but I followed the guides and eventually got the basic server running."
        }
    
    # Day 7, 8, 9, 10: Embeddings, ChromaDB, and Retrieval
    elif any(k in q for k in ["embeddings", "sentence transformers", "vector", "day 7"]):
        return {
            "strong": "I selected 'all-MiniLM-L6-v2' to generate 384-dimensional dense vectors because of its low latency and solid performance. I tested the embedding space by running PCA clustering in Matplotlib to verify that healthcare plans grouped correctly.",
            "vague": "I imported Sentence Transformers, converted our text into list of floating numbers, and ran similarity tests using cosine distance.",
            "gap": "To be transparent, I skipped the Day 7 embeddings mission. I understand they convert text into numerical vectors, but I haven't configured the models myself."
        }
        
    elif any(k in q for k in ["chromadb", "pinecone", "database", "day 8", "day 9"]):
        return {
            "strong": "I set up ChromaDB locally for our vector store. I mapped the text chunks with precise metadata schemas (plan names and document sections) to allow for efficient pre-filtering before running vector similarity searches.",
            "vague": "We ran a local Chroma database, saved our document vectors there, and queried them using similarity searches when users asked questions.",
            "gap": "I skipped the vector database setup module. I know they index embeddings for fast retrieval, but I haven't done any production setup for ChromaDB."
        }
        
    elif any(k in q for k in ["retrieval", "matching", "hybrid", "day 10"]):
        return {
            "strong": "I built a unified query router that dynamically shifts between structured SQL queries (using SQLAlchemy on SQLite) for specific claims/plans and vector similarity searches in ChromaDB for unstructured queries, implementing clean deduplication.",
            "vague": "I wrote a Python routing script that checks if a query needs a database lookup or semantic search, and then merges the results.",
            "gap": "I didn't complete the Day 10 retrieval engine mission, so my project relies on basic similarity lookup without SQL routing or hybrid deduplication."
        }

    # Day 11, 12, 13, 14, 15: LLM, Prompting, Function Calling, Fine-Tuning
    elif any(k in q for k in ["prompt", "system prompt", "day 12", "few-shot", "chain-of-thought"]):
        return {
            "strong": "I designed a grounded system prompt template that restricts the LLM to only answer from retrieved chunks, implementing few-shot examples and chain-of-thought instructions to reduce hallucinations in healthcare plans.",
            "vague": "I wrote a standard prompt telling the model to act as a helpful healthcare assistant and only use the provided text to answer.",
            "gap": "I struggled with prompt engineering and mostly relied on the default OpenAI/Groq system prompts without fine-tuning templates or chain-of-thought guardrails."
        }
        
    elif any(k in q for k in ["function calling", "pydantic", "structured output", "day 13"]):
        return {
            "strong": "I defined strict Pydantic v2 schemas for our database models and tools, enabling OpenAI/Groq function calling to invoke real-time SQL calculations on claims while automatically validating the JSON payload.",
            "vague": "I set up JSON schemas for the functions so the model knows which function to call, and parsed the model's response dictionary.",
            "gap": "I didn't complete the function calling mission because I found Pydantic schema generation confusing. I used standard string parsing instead."
        }
        
    elif any(k in q for k in ["fine-tuning", "lora", "qlora", "day 14", "day 15"]):
        return {
            "strong": "We evaluated LoRA and QLoRA for fine-tuning a local model. While prompting with RAG is better for dynamic document queries, we found fine-tuning highly effective for enforcing a specific, empathetic medical tone and structured output format.",
            "vague": "I prepared a JSONL training dataset with some example questions and answers, and looked at how to run fine-tuning on a local model.",
            "gap": "Our team explicitly skipped the fine-tuning days as it was out of scope for our initial prototype, focusing instead on optimizing our prompt templates."
        }

    # Day 16, 17, 18, 20: FastAPI, Frontend, Streaming, Memory
    elif any(k in q for k in ["streaming", "server-sent events", "day 18"]):
        return {
            "strong": "I implemented an asynchronous streaming endpoint in FastAPI using StreamingResponse and Server-Sent Events, allowing tokens to render incrementally in Streamlit using st.write_stream to improve perceived latency.",
            "vague": "I modified the FastAPI endpoint to stream the responses back, and used Streamlit's built-in streaming features to display them.",
            "gap": "I skipped the streaming response day, so the frontend waits for the entire backend API response to finish before displaying the text."
        }
        
    elif any(k in q for k in ["memory", "context", "day 20"]):
        return {
            "strong": "I persisted chat logs in SQLite and built a rolling token window manager. For longer conversations, I implement automatic summary extraction to compress past turns, staying well within Groq's context window.",
            "vague": "We stored the conversation history in a list in the session state, and sent the last few messages back to the LLM on every turn.",
            "gap": "I didn't implement conversation memory persistence, so every time the webpage refreshes, the previous chat history is completely wiped."
        }

    # Day 21, 22, 23, 24: Agents, CrewAI, LangGraph, MCP
    elif any(k in q for k in ["agent", "crewai", "langgraph", "orchestration", "day 21", "day 22"]):
        return {
            "strong": "I designed a multi-agent system using LangGraph where a routing agent delegates specialized tasks to a SQL searcher or a medical text reader, managing state transitions and conflict resolution via clean graph-based conditions.",
            "vague": "I used a simple agent framework to combine our database tools, allowing the agent to choose between searching plans or checking claims.",
            "gap": "I skipped the agentic orchestration days. I understand the theoretical benefits of multi-agent collaboration, but my chatbot uses a single sequential pipeline."
        }
        
    elif any(k in q for k in ["mcp", "model context", "day 23"]):
        return {
            "strong": "I built a custom Model Context Protocol (MCP) server in Python, exposing our healthcare database tools. This allows MCP-compliant clients like Claude Desktop to securely query our backend schemas using standardized json-rpc interfaces.",
            "vague": "I set up an MCP server that lists our tools, and connected it to Claude so it can search our databases directly.",
            "gap": "I skipped the Model Context Protocol module. I understand it standardizes how LLMs interact with external tools, but I haven't built an MCP server."
        }

    # Day 27, 28, 29, 31: Security, Docker, Kubernetes, Monitoring, Observability
    elif any(k in q for k in ["docker", "kubernetes", "container", "day 28"]):
        return {
            "strong": "I containerized our FastAPI backend and React frontend into multi-stage Docker builds to minimize image sizes. I deployed them to a local Kubernetes cluster, configuring service discovery, ConfigMaps for API keys, and resource limits.",
            "vague": "I wrote a Dockerfile for the app, built the container image, and set up a deployment yaml to run it inside a Kubernetes cluster.",
            "gap": "I skipped the containerization and Kubernetes days. I understand they help scale apps, but I ran the prototype directly on my local computer."
        }
        
    elif any(k in q for k in ["monitoring", "observability", "prometheus", "grafana", "day 29"]):
        return {
            "strong": "I integrated Python's logging module to output structured JSON logs. I set up Prometheus to scrape custom API metrics—tracking route latencies and LLM token counts—and built a Grafana dashboard for real-time visualization.",
            "vague": "We added print statements and log files in our FastAPI backend to track requests and errors, and monitored server CPU usage.",
            "gap": "I skipped the Day 29 monitoring module. I understand why structured telemetry and scraping metrics with Prometheus is critical for SLA, but didn't build it."
        }

    # Default fallback if no keyword matches — make it candidate-specific and professional!
    return {
        "strong": f"In my role as a {role}, I approached this challenge with a focus on system integrity. I ensured our APIs were asynchronous, validated all schemas using Pydantic, and verified the output matched our performance expectations.",
        "vague": "I completed the implementation by following the provided specifications. Everything was tested locally and integrated with the main backend branch.",
        "gap": f"To be honest, that specific area was one of the more challenging parts of the 31-day cohort for me. I focused my time on the core RAG and API integration first."
    }

# ──────────────────────────────────────────────────────────────────────────────
# Session state initialisation
# ──────────────────────────────────────────────────────────────────────────────
def _init_session() -> None:
    """Ensure all required keys exist in st.session_state."""
    defaults = {
        "session_id": str(uuid.uuid4()),
        "messages": [],  # list of {"role": "user"|"assistant", "content": str}
        "interview_started": False,
        "feedback": None,  # populated when backend returns a feedback object
        "selected_idx": 0,
        "last_selected_cand_id": None,
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
    POST /api/interview — wraps both first-turn (with candidate) and subsequent turns.
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
    member = candidate["member"]
    signals = candidate.get("signals", {})
    now = datetime.now().strftime("%B %d, %Y · %H:%M")
    
    strengths = "\n".join(f"- ✓ {s}" for s in feedback.get("strengths", []))
    gaps = "\n".join(f"- △ {g}" for g in feedback.get("gaps", []))
    next_steps = "\n".join(
        f"{i + 1}. {n}" for i, n in enumerate(feedback.get("next", []))
    )
    
    return f"""# Technical Readiness Assessment

> **Generated by AI Cohort Interview Agent · {now}**

---

## Candidate Profile

| Field | Value |
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

*This evaluation was generated automatically by the AI Cohort Interview Agent. Results should be reviewed by a senior technical hiring manager before making final placement decisions.*
"""

# ──────────────────────────────────────────────────────────────────────────────
# UI Components
# ──────────────────────────────────────────────────────────────────────────────
def render_bio_card(candidate: Dict[str, Any]) -> None:
    member = candidate["member"]
    signals = candidate.get("signals", {})
    rate = first_try_rate(signals)
    status_cls = "badge-green" if member["status"] == "COMPLETED" else "badge-blue"

    # Header: name / role / details — rendered as HTML (safe in main area + sidebar)
    st.markdown(
        f"""
        <div class="bio-card-container">
            <div class="bio-name">{member['name']}</div>
            <div class="bio-role">{member['jobRole']}</div>
            <div class="bio-detail">Education: <span>{member['education']}</span></div>
            <div class="bio-detail">Experience: <span>{member['yearsExperience']} Years</span></div>
            <div class="bio-detail">Status: <span class="status-badge {status_cls}">{member['status']}</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # KPI tiles — use native st.metric so Streamlit Cloud renders them correctly
    k1, k2, k3 = st.columns(3)
    k1.metric("Commit Days", signals.get("commitDays", "—"))
    k2.metric("Completed", signals.get("missionsCompleted", "—"))
    k3.metric("First Try", f"{rate}%")

def render_mission_timeline(candidate: Dict[str, Any]) -> None:
    """Render colored mission pills across the top of the main area."""
    st.markdown(
        """
        <div class="timeline-container">
            <div class="timeline-title">
                📅 Curriculum Journey & Competency Map
            </div>
            <div class="timeline-grid">
        """,
        unsafe_allow_html=True,
    )
    pills_html = ""
    for mission in candidate.get("missions", []):
        day = mission.get("day", "?")
        title = mission.get("title", f"Day {day}")
        short = title[:20] + "..." if len(title) > 22 else title
        
        if mission.get("passed"):
            attempts = mission.get("attempts", 1)
            label = f"✓ Day {day}: {short} [{attempts}×]"
            cls = "pill-pass"
        elif mission.get("skipped"):
            label = f"◌ Day {day}: {short} [Skipped]"
            cls = "pill-skip"
        else:
            attempts = mission.get("attempts", "?")
            label = f"✗ Day {day}: {short} [{attempts}×]"
            cls = "pill-fail"
            
        pills_html += f'<span class="pill-badge {cls}">{label}</span>'
        
    st.markdown(pills_html, unsafe_allow_html=True)
    st.markdown("</div></div>", unsafe_allow_html=True)

def render_feedback_panel(feedback: Dict[str, Any], candidate: Dict[str, Any]) -> None:
    """Render the full Technical Readiness Assessment panel."""
    member = candidate["member"]
    
    st.markdown(
        f"""
        <div class="assessment-card">
            <div class="assessment-header">
                🏆 Technical Readiness Assessment
                <div style="font-size:0.95rem; font-weight:400; color:#94A3B8; margin-top:0.35rem;">
                    Candidate: {member['name']} · {member['jobRole']} · Evaluated {datetime.now().strftime("%B %d, %Y")}
                </div>
            </div>
        """,
        unsafe_allow_html=True,
    )
    
    # Executive Summary
    st.markdown(
        f"""
        <div class="assessment-block">
            <div class="assessment-block-title">📋 Executive Summary</div>
            <div style="font-size:0.95rem; line-height:1.6; color:#E2E8F0;">
                {feedback.get("summary", "No summary available.")}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    
    # Strengths & Gaps — two columns
    col_l, col_r = st.columns(2)
    with col_l:
        st.markdown('<div class="section-header">💪 Identified Strengths</div>', unsafe_allow_html=True)
        strengths = feedback.get("strengths", [])
        if strengths:
            for s in strengths:
                st.markdown(
                    f'<div class="assessment-block card-strengths">{s}</div>',
                    unsafe_allow_html=True,
                )
        else:
            st.info("No strengths recorded.")
            
    with col_r:
        st.markdown('<div class="section-header">⚠️ Identified Gaps</div>', unsafe_allow_html=True)
        gaps = feedback.get("gaps", [])
        if gaps:
            for g in gaps:
                st.markdown(
                    f'<div class="assessment-block card-gaps">{g}</div>',
                    unsafe_allow_html=True,
                )
        else:
            st.success("No significant gaps identified.")
            
    # Next steps
    st.markdown('<div class="section-header">🗺️ Actionable Learning Roadmap</div>', unsafe_allow_html=True)
    next_steps = feedback.get("next", [])
    for i, step in enumerate(next_steps, 1):
        st.markdown(
            f'<div class="assessment-block card-step"><strong>Step {i}:</strong> {step}</div>',
            unsafe_allow_html=True,
        )
        
    st.markdown("</div>", unsafe_allow_html=True)
    
    # Download report
    st.markdown("---")
    report_md = build_markdown_report(candidate, feedback)
    st.download_button(
        label="⬇️ Download Full Evaluation Report (.md)",
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
            """
            <div class="sidebar-title">🤖 AI Cohort</div>
            <div class="sidebar-subtitle">Adaptive Technical Interviewer</div>
            """,
            unsafe_allow_html=True,
        )
        st.divider()
        
        # API URL config
        st.markdown("**🌐 Backend API URL**")
        api_url = st.text_input(
            "API URL",
            value="https://ai-cohort-seven.vercel.app",
            label_visibility="collapsed",
            key="api_url",
        )
        st.caption("Change to `http://localhost:8000` for local dev.")
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
        
        # Detect if candidate changed -> automatically reset state
        current_cand_id = selected_candidate["member"]["id"]
        if st.session_state.last_selected_cand_id != current_cand_id:
            st.session_state.last_selected_cand_id = current_cand_id
            reset_session()
            st.rerun()
            
        # Bio card + KPIs
        render_bio_card(selected_candidate)
        st.divider()
        
        # Reset / Start
        if st.button("🔄 Reset Session", use_container_width=True):
            reset_session()
            st.rerun()
            
        if st.session_state.interview_started:
            st.caption(f"Active Session: `{st.session_state.session_id[:8]}…`")
            
    # ── MAIN AREA ──────────────────────────────────────────────────────────────
    st.markdown(
        """
        <div class="top-banner">
            <div class="top-title">🤖 Cohort Interview Simulator</div>
            <div class="top-subtitle">
                An adaptive, multi-turn AI assessor evaluating software engineers on their enterprise chatbot curriculum.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    
    # Competency map
    render_mission_timeline(selected_candidate)
    
    # ── AUTO-GREETING (Zero-Click Start) ──────────────────────────────────────
    # If the session is uninitialized and has zero messages, automatically ping the API to greet
    if not st.session_state.interview_started and len(st.session_state.messages) == 0:
        with st.spinner("AI Interviewer is analyzing the candidate profile and preparing the greeting..."):
            try:
                result = call_interview_api(
                    base_url=api_url,
                    session_id=st.session_state.session_id,
                    candidate=selected_candidate,
                    message=None,
                )
                st.session_state.interview_started = True
                agent_msg = result.get("message", "")
                if agent_msg:
                    st.session_state.messages.append({"role": "assistant", "content": agent_msg})
                st.rerun()
            except Exception as exc:
                st.error(
                    "⚠️ **Could not connect to backend to start session.**\n\n"
                    f"Please verify that your backend server is active at **`{api_url}`**.\n\n"
                    f"Error details: {exc}"
                )
                return

    # ── CHAT SECTION ──────────────────────────────────────────────────────────
    # If feedback has been returned, show the panel instead of the chat input
    if st.session_state.feedback:
        # Replay conversation in collapsed expander
        with st.expander("💬 View Full Conversation Transcript", expanded=False):
            for msg in st.session_state.messages:
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])
        render_feedback_panel(st.session_state.feedback, selected_candidate)
        return

    # Replay stored conversation history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # ── ONE-CLICK SIMULATED ANSWERS (Context-Aware Interactivity Booster) ─────
    # Extract last question from interviewer to tailor the quick response options
    last_assistant_msg = ""
    for msg in reversed(st.session_state.messages):
        if msg["role"] == "assistant":
            last_assistant_msg = msg["content"]
            break
            
    dynamic_replies = get_dynamic_simulated_answers(last_assistant_msg, selected_candidate)
    
    st.markdown(
        '<div class="helper-header">💡 Contextual Responses (Test Llama-3.3 As Candidate)</div>',
        unsafe_allow_html=True,
    )
    
    simulated_reply = None
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        if st.button("💪 Strong Technical Answer", use_container_width=True, help="Submit an in-depth, curriculum-specific response."):
            simulated_reply = dynamic_replies["strong"]
    with col_b:
        if st.button("⚠️ Vague / Basic Answer", use_container_width=True, help="Submit a high-level, superficial answer."):
            simulated_reply = dynamic_replies["vague"]
    with col_c:
        if st.button("🔍 Admit Gap (Skip/Failed)", use_container_width=True, help="Honest admission of weakness on this topic."):
            simulated_reply = dynamic_replies["gap"]

    # ── CHAT INPUT & SUBMISSION ──────────────────────────────────────────────
    user_input = st.chat_input("Type your custom answer and press Enter…")
    
    # Process input (either from chat box or simulated button)
    final_input = simulated_reply or user_input
    
    if final_input is not None:
        # Save and render user message
        st.session_state.messages.append({"role": "user", "content": final_input})
        with st.chat_message("user"):
            st.markdown(final_input)
            
        # Call backend
        with st.spinner("Interviewer is evaluating your response…"):
            try:
                result = call_interview_api(
                    base_url=api_url,
                    session_id=st.session_state.session_id,
                    candidate=None,
                    message=final_input,
                )
                
                agent_msg = result.get("message", "")
                feedback = result.get("feedback")
                
                # Store and display agent response
                if agent_msg:
                    st.session_state.messages.append({"role": "assistant", "content": agent_msg})
                    
                # If feedback was returned, store it
                if feedback:
                    st.session_state.feedback = feedback
                    
                st.rerun()
                
            except requests.exceptions.ConnectionError:
                st.warning(
                    "⚠️ **Connection Error** — Could not reach the backend API. "
                    f"Please check the API URL: `{api_url}`"
                )
            except requests.exceptions.Timeout:
                st.warning(
                    "⏱️ **Timeout** — The backend took too long to respond. "
                    "Vercel serverless cold starts can take up to 30 seconds."
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
