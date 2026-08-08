"""
app/services/prompt_builder.py

Dynamic, persona-aware system prompt assembly for the AI Interview Agent.

Responsibilities:
  1. Load the 31-day curriculum from data/curriculum.json at startup.
  2. Cross-reference the candidate's mission history (passed / skipped) against
     the curriculum to inject richly grounded day-by-day context.
  3. Apply persona-specific probing instructions based on the candidate's
     professional background and years of experience.
  4. Return a complete, ready-to-send system prompt string.

Usage:
    from app.services.prompt_builder import prompt_builder  # singleton

    system_prompt = prompt_builder.build_system_prompt(candidate_data_dict)
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Curriculum path resolution
# ---------------------------------------------------------------------------

# Resolve relative to THIS file so the path is absolute and Vercel-safe.
# File lives at:  <project_root>/app/services/prompt_builder.py
# Curriculum at:  <project_root>/data/curriculum.json
_DEFAULT_CURRICULUM_PATH = str(
    Path(__file__).resolve().parent.parent.parent / "data" / "curriculum.json"
)


# ---------------------------------------------------------------------------
# Persona probing instructions
# ---------------------------------------------------------------------------

_PERSONA_PROBING: Dict[str, str] = {
    # Senior data engineering profile
    "data engineer": (
        "This candidate is an experienced **Senior Data Engineer**. Prioritise questions on: "
        "schema design, pipeline optimisation, distributed data processing, production database "
        "performance (indexing, partitioning, vacuum), vector store scaling strategies, and "
        "monitoring/alerting for data workflows. Challenge their architectural choices — ask WHY "
        "they selected a tool over alternatives."
    ),
    # Backend / software engineering profile
    "backend": (
        "This candidate is a **Backend Software Engineer**. Focus on: system design trade-offs, "
        "RESTful API design, function calling implementation details, async patterns (asyncio, "
        "background tasks), rate-limiting, caching strategies, and CI/CD pipeline design. "
        "Ask how they would handle high-concurrency loads and service failures."
    ),
    "software engineer": (
        "This candidate is a **Backend Software Engineer**. Focus on: system design trade-offs, "
        "RESTful API design, function calling implementation details, async patterns (asyncio, "
        "background tasks), rate-limiting, caching strategies, and CI/CD pipeline design."
    ),
    # Marketing / non-technical profile
    "marketing": (
        "This candidate has a **Marketing/Business background**. Adapt accordingly: avoid deep "
        "implementation questions. Instead, probe practical application understanding — how they "
        "configured environment variables, understood API responses, and used guardrails or safety "
        "filters. Assess their ability to explain AI concepts to non-technical stakeholders."
    ),
    "manager": (
        "This candidate comes from a **business/management background**. Assess conceptual "
        "understanding and practical application rather than implementation depth. Probe their "
        "ability to evaluate AI tools, manage AI projects, and apply governance principles."
    ),
    # AI / ML engineering profile
    "ai engineer": (
        "This candidate is an **AI Engineer**. Probe at the deepest level: advanced multi-agent "
        "orchestration patterns, Model Context Protocol (MCP) server-client configuration, "
        "retrieval architecture optimisation (HyDE, cross-encoder reranking), fine-tuning "
        "trade-offs, and production observability for LLM pipelines. Expect architectural "
        "justifications backed by empirical evidence."
    ),
    "ml engineer": (
        "This candidate is an **ML Engineer**. Focus on: model evaluation, fine-tuning, RAG "
        "optimisation, vector similarity metrics, embedding model selection, and production "
        "deployment patterns."
    ),
}

# Fallback for unrecognised roles
_DEFAULT_PERSONA = (
    "This candidate is a technical professional. Balance conceptual questions with practical "
    "implementation probes. Adapt depth based on their answers."
)


def _match_persona(job_role: str) -> str:
    """Return the best-matching persona instruction for the given job role string."""
    role_lower = job_role.lower()
    for keyword, instruction in _PERSONA_PROBING.items():
        if keyword in role_lower:
            return instruction
    return _DEFAULT_PERSONA


# ---------------------------------------------------------------------------
# PromptBuilder class
# ---------------------------------------------------------------------------


class PromptBuilder:
    """
    Builds highly personalised, curriculum-grounded system prompts.

    The curriculum is loaded once at initialisation and cached in memory.
    The `build_system_prompt` method is called per request (not expensive —
    it's pure string formatting on already-loaded data).
    """

    def __init__(self, curriculum_path: str = _DEFAULT_CURRICULUM_PATH) -> None:  # noqa: E501
        self._curriculum_path = curriculum_path
        self._curriculum: Dict[str, Any] = self._load_curriculum()
        # Build a quick lookup dict: day_number → curriculum_day_dict
        self._day_index: Dict[int, Dict[str, Any]] = {
            d["day"]: d for d in self._curriculum.get("days", [])
        }
        logger.info(
            "PromptBuilder initialised with curriculum_path=%s, days_loaded=%d",
            curriculum_path,
            len(self._day_index),
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_curriculum(self) -> Dict[str, Any]:
        """Load curriculum JSON from disk. Returns empty structure on failure."""
        if not Path(self._curriculum_path).exists():
            logger.warning(
                "Curriculum file not found at %s — PromptBuilder will operate without it.",
                self._curriculum_path,
            )
            return {"days": []}
        try:
            with open(self._curriculum_path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
                logger.info("Curriculum loaded: %d days", len(data.get("days", [])))
                return data
        except (json.JSONDecodeError, OSError) as exc:
            logger.error("Failed to load curriculum: %s", exc)
            return {"days": []}

    def _build_curriculum_context(
        self,
        missions: List[Dict[str, Any]],
    ) -> str:
        """
        Cross-reference the candidate's missions with the curriculum to produce
        a structured, day-by-day context block for the system prompt.

        Example output line:
          - Day 7: Embeddings Explained [COMPLETED — 1 attempt]
              Tools: Sentence Transformers, OpenAI text-embedding-ada-002, NumPy, Matplotlib, PCA
              Objectives: Convert text to high-dimensional vector embeddings using Sentence Transformers;
                          Understand cosine similarity and Euclidean distance metrics; ...
        """
        lines: List[str] = []
        for mission in missions:
            day_num = mission.get("day")
            if day_num is None:
                continue

            curriculum_day = self._day_index.get(day_num)

            # Determine status label
            if mission.get("passed"):
                attempts = mission.get("attempts", 1)
                attempt_label = f"{attempts} attempt{'s' if attempts != 1 else ''}"
                status_label = f"COMPLETED — {attempt_label}"
            elif mission.get("skipped"):
                status_label = "SKIPPED ⚠️"
            else:
                status_label = "IN PROGRESS"

            title = mission.get("title", f"Day {day_num}")
            line = f"  • Day {day_num}: {title} [{status_label}]"

            if curriculum_day:
                tools = curriculum_day.get("tools", [])
                objectives = curriculum_day.get("objectives", [])
                if tools:
                    line += f"\n      Tools used: {', '.join(tools)}"
                if objectives:
                    objective_text = "; ".join(objectives[:2])
                    line += f"\n      Key objectives: {objective_text}"

            lines.append(line)

        return "\n".join(lines) if lines else "  (No mission data available)"

    def _build_skipped_day_notes(self, missions: List[Dict[str, Any]]) -> str:
        """Return a formatted note about skipped days for the interviewer to probe carefully."""
        skipped = [m for m in missions if m.get("skipped")]
        if not skipped:
            return ""

        notes: List[str] = []
        for m in skipped:
            day_num = m.get("day")
            title = m.get("title", f"Day {day_num}")
            curriculum_day = self._day_index.get(day_num, {})
            objectives = curriculum_day.get("objectives", [])
            note = f"  • Day {day_num}: {title}"
            if objectives:
                note += f" — Key concepts they may lack: {'; '.join(objectives[:2])}"
            notes.append(note)
        return "\n".join(notes)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def build_system_prompt(self, candidate_data: Dict[str, Any]) -> str:
        """
        Assemble and return the complete system prompt for the LLM.

        Args:
            candidate_data: Dict representation of the Candidate Pydantic model
                            (use `candidate.model_dump()`).

        Returns:
            A multi-section system prompt string ready to be passed to the LLM
            as the first message with role="system".
        """
        member = candidate_data.get("member", {})
        name: str = member.get("name", "the candidate")
        job_role: str = member.get("jobRole", "Professional")
        years_exp: int = member.get("yearsExperience", 0)
        education: str = member.get("education", "Not specified")
        cohort_status: str = member.get("status", "COMPLETED")

        missions: List[Dict[str, Any]] = candidate_data.get("missions", [])
        signals: Dict[str, Any] = candidate_data.get("signals", {})

        commit_days: int = signals.get("commitDays", 0)
        missions_completed: int = signals.get("missionsCompleted", 0)
        missions_first_try: int = signals.get("missionsFirstTry", 0)

        # Derive first-try rate for signal analysis
        first_try_pct = (
            round((missions_first_try / missions_completed) * 100)
            if missions_completed > 0
            else 0
        )

        curriculum_context = self._build_curriculum_context(missions)
        skipped_notes = self._build_skipped_day_notes(missions)
        persona_instructions = _match_persona(job_role)

        # Build skipped section only if there are skipped days
        skipped_section = ""
        if skipped_notes:
            skipped_section = f"""
### ⚠️ Skipped Days — High-Priority Probing Targets
The candidate deliberately skipped the following curriculum days. You MUST probe around these
topics to identify whether they still possess working knowledge, or flag it as a genuine gap:
{skipped_notes}
"""

        prompt = f"""You are an elite, world-class technical interviewer conducting a high-stakes
multi-turn technical interview for {name}. They are a {years_exp}-year experienced {job_role}
with a {education} degree who has just completed an intensive 31-day Enterprise AI Engineering
Cohort (status: {cohort_status}).

═══════════════════════════════════════════════════════════════
 CANDIDATE PERFORMANCE SIGNALS
═══════════════════════════════════════════════════════════════
  Active Commit Days  : {commit_days}/31
  Missions Completed  : {missions_completed}
  First-Try Pass Rate : {first_try_pct}% ({missions_first_try}/{missions_completed} missions)

═══════════════════════════════════════════════════════════════
 CANDIDATE'S CURRICULUM LEARNING PATH
═══════════════════════════════════════════════════════════════
{curriculum_context}
{skipped_section}
═══════════════════════════════════════════════════════════════
 PERSONA-SPECIFIC INTERVIEWER INSTRUCTIONS
═══════════════════════════════════════════════════════════════
{persona_instructions}

═══════════════════════════════════════════════════════════════
 UNIVERSAL INTERVIEWER RULES (MANDATORY)
═══════════════════════════════════════════════════════════════
1. CONVERSATIONAL FLOW: Conduct a natural, adaptive conversation. Do NOT follow a rigid script.
   React intelligently to what the candidate says. If they mention a tool, library, or decision —
   probe it. Ask WHY they chose it over alternatives. Ask about bottlenecks and trade-offs.

2. MINIMUM COVERAGE: Ask at MINIMUM 8 questions. Cover at LEAST 4 distinct curriculum days.
   Spread questions across the candidate's learning path — do not fixate on a single topic.

3. ONE QUESTION PER TURN: You may ONLY ask a single question per response. Never ask
   multiple questions in the same message. This is a hard rule.

4. ADAPTIVE FOLLOW-UP: When the candidate gives an answer that references specific tools,
   architectures, configurations, or decisions — immediately formulate a deep, targeted
   follow-up. Examples:
   - "You mentioned ChromaDB — how did you handle metadata filtering for multi-tenant queries?"
   - "You used all-MiniLM-L6-v2 — how would you evaluate whether that embedding model provides
     sufficient semantic resolution for your domain compared to a larger model?"

5. ADAPTIVE DEPTH: Calibrate difficulty to the candidate's background. {name} has {years_exp}
   years as a {job_role} — expect architectural-level answers. Lower the bar for candidates
   from non-engineering backgrounds.

6. SKIPPED DAY HANDLING: If the candidate claims knowledge of a topic they skipped in the
   curriculum, probe it carefully. If they show genuine gaps, note it gracefully and move on.
   Do NOT embarrass the candidate.

7. PROFESSIONAL TONE: Be warm, encouraging, and professional. This interview should feel like
   a high-quality, respected technical conversation — not an interrogation.

8. COMPLETION SIGNAL: Once you have asked 8+ questions covering 4+ curriculum days AND have
   gathered enough signal to evaluate the candidate, conclude the interview with a warm,
   professional closing message. Then output the structured feedback object.

Begin the interview now with a warm, personalised greeting followed immediately by your
first technical question targeting the candidate's first completed curriculum day.
"""
        return prompt.strip()


# ---------------------------------------------------------------------------
# Module-level singleton — import this in other modules
# ---------------------------------------------------------------------------

prompt_builder = PromptBuilder()
