"""
app/main.py

AI Cohort Interview Agent — FastAPI Application Entry Point.

Endpoints:
  POST /api/interview      — Unified interview turn handler (init + conversation + feedback)
  GET  /api/health         — Health check with active session count
  GET  /api/session/{id}   — Session metadata inspector

State Machine (per session):
  GREETING → INTERVIEW → FEEDBACK_COMPILE → COMPLETED

Heuristic Day Tracking:
  Days discussed are tracked by the API based on question_count milestones.
  This is an intentional heuristic: the LLM naturally covers topics in sequence,
  so the API approximates day coverage based on turn count. A production system
  would parse LLM responses to extract mentioned day numbers precisely.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.schemas import Candidate, InterviewRequest, InterviewResponse
from app.services.llm import llm_service
from app.services.prompt_builder import prompt_builder
from app.state.session import InterviewState, session_manager

# ---------------------------------------------------------------------------
# Environment & logging setup
# ---------------------------------------------------------------------------

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="AI Cohort Interview Agent",
    description=(
        "Production-grade stateful AI Interview Agent that conducts adaptive, "
        "multi-turn technical interviews using OpenAI GPT-4o and curriculum-grounded prompts."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)


# ---------------------------------------------------------------------------
# Exception handlers
# ---------------------------------------------------------------------------


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Return a clean 422 with a human-readable error list."""
    errors = []
    for error in exc.errors():
        field = " → ".join(str(loc) for loc in error["loc"])
        errors.append({"field": field, "message": error["msg"]})
    logger.warning(
        "Request validation error on %s: %d error(s)",
        request.url.path,
        len(errors),
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": "Request schema validation failed", "errors": errors},
    )


@app.exception_handler(Exception)
async def generic_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    """Catch-all 500 handler — logs the error and returns a safe message."""
    logger.error(
        "Unhandled exception on %s: %s",
        request.url.path,
        exc,
        exc_info=True,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "An internal server error occurred. Please try again shortly."
        },
    )


# ---------------------------------------------------------------------------
# Helper: derive curriculum day numbers from a candidate object
# ---------------------------------------------------------------------------


def _get_mission_days_by_status(
    candidate: Candidate,
    status_key: str,
) -> list[int]:
    """Return sorted list of day numbers for missions matching `status_key` (passed/skipped)."""
    return sorted(
        m.day for m in candidate.missions if getattr(m, status_key, False)
    )


def _get_first_passed_day(candidate: Candidate) -> int | None:
    """Return the day number of the earliest passed mission, or None."""
    passed_days = _get_mission_days_by_status(candidate, "passed")
    return passed_days[0] if passed_days else None


# ---------------------------------------------------------------------------
# Helper: heuristic day tracking
# ---------------------------------------------------------------------------

# Map question_count checkpoints → curriculum day to add to days_discussed.
# These are the milestone-based day coverage approximations.
_DAY_UNLOCK_CHECKPOINTS: Dict[int, int] = {
    3: 2,   # ~question 3 → unlock day 2 (following first question day)
    5: 3,   # ~question 5 → unlock day 3
    7: 4,   # ~question 7 → unlock day 4
}


def _advance_day_tracking(session, candidate: Candidate) -> None:
    """
    Heuristically expand the days_discussed set based on question_count.

    Uses the candidate's actual passed mission day numbers to stay curriculum-accurate.
    Falls back to incrementing pseudo-day numbers if not enough missions exist.

    Must be called inside a session.lock context.
    """
    passed_days = _get_mission_days_by_status(candidate, "passed")

    checkpoint_to_day_index = {
        3: 1,   # second passed day (index 1)
        5: 2,   # third passed day
        7: 3,   # fourth passed day
    }

    for checkpoint, day_index in checkpoint_to_day_index.items():
        if session.question_count >= checkpoint:
            if day_index < len(passed_days):
                session.days_discussed.add(passed_days[day_index])


# ---------------------------------------------------------------------------
# Main interview endpoint
# ---------------------------------------------------------------------------


@app.post(
    "/api/interview",
    response_model=InterviewResponse,
    summary="Conduct an interview turn",
    description=(
        "Unified endpoint for all interview interactions. "
        "Supply `candidate` on the first call to initialise a session. "
        "Supply `message` on subsequent calls to continue the conversation."
    ),
)
async def handle_interview_turn(request: InterviewRequest) -> InterviewResponse:
    """
    POST /api/interview

    Handles all three interview phases:
      1. Initialisation (GREETING): Creates session, generates personalised opening question.
      2. Conversation (INTERVIEW): Appends candidate message, generates follow-up question.
      3. Evaluation (FEEDBACK_COMPILE → COMPLETED): Compiles and returns structured Feedback.
    """
    session_id = request.sessionId
    session = session_manager.get_session(session_id)

    # -----------------------------------------------------------------------
    # Phase 1: Initialise new session
    # -----------------------------------------------------------------------
    if session is None:
        logger.info("session=%s New session request received", session_id)

        if not request.candidate:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "A valid 'candidate' payload is required to start a new interview session. "
                    "Send 'candidate' on the first request to initialise the session."
                ),
            )

        # Create thread-safe session
        try:
            session = session_manager.create_session(session_id, request.candidate)
        except ValueError as exc:
            # Race condition: another thread created the session between our get/create
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(exc),
            )

        # Build system prompt from candidate + curriculum data
        system_prompt = prompt_builder.build_system_prompt(request.candidate.model_dump())

        # Compose a targeted greeting instruction for the LLM
        first_day = _get_first_passed_day(request.candidate)
        first_day_context = (
            f"Day {first_day}" if first_day else "their first completed curriculum module"
        )
        greeting_user_msg = (
            f"Please start the interview now. Greet {request.candidate.member.name} warmly "
            f"by name, briefly acknowledge their background as a "
            f"{request.candidate.member.jobRole} with {request.candidate.member.yearsExperience} "
            f"years of experience, and immediately ask your first technical question based on "
            f"{first_day_context} from their completed curriculum."
        )

        # Call LLM (no history yet — fresh session)
        initial_msg, _ = llm_service.generate_interview_response(
            system_prompt=system_prompt,
            history=[{"role": "user", "content": greeting_user_msg}],
            is_final_turn=False,
        )

        # Persist state
        with session.lock:
            session.add_message("assistant", initial_msg)
            session.question_count = 1
            if first_day is not None:
                session.days_discussed.add(first_day)
            session.advance_state(InterviewState.INTERVIEW)

        logger.info(
            "session=%s Greeted candidate=%s, first_day=%s",
            session_id,
            request.candidate.member.name,
            first_day,
        )
        return InterviewResponse(sessionId=session_id, message=initial_msg)

    # -----------------------------------------------------------------------
    # Phase 2 & 3: Ongoing session
    # -----------------------------------------------------------------------

    if not request.message:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "An active session exists. Please provide a 'message' to continue the interview."
            ),
        )

    with session.lock:
        # Guard: reject messages to completed sessions
        if session.state == InterviewState.COMPLETED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Session '{session_id}' has already been completed and is closed. "
                    "Start a new session with a fresh sessionId."
                ),
            )

        # Append candidate's message to history
        session.add_message("user", request.message)
        session.question_count += 1

        # Heuristically expand days_discussed coverage
        _advance_day_tracking(session, session.candidate)

        logger.info(
            "session=%s turn=%d days_covered=%d message_preview='%.60s...'",
            session_id,
            session.question_count,
            len(session.days_discussed),
            request.message,
        )

        # Check termination criteria
        is_final_turn = session.meets_completion_criteria
        system_prompt = prompt_builder.build_system_prompt(session.candidate.model_dump())

        # -----------------------------------------------------------------------
        # Phase 3: Compile feedback (final turn)
        # -----------------------------------------------------------------------
        if is_final_turn:
            logger.info(
                "session=%s Termination criteria met — compiling feedback "
                "(questions=%d, days=%d)",
                session_id,
                session.question_count,
                len(session.days_discussed),
            )
            session.advance_state(InterviewState.FEEDBACK_COMPILE)

            concluding_msg, feedback_obj = llm_service.generate_interview_response(
                system_prompt=system_prompt,
                history=session.history,
                is_final_turn=True,
            )

            session.add_message("assistant", concluding_msg)
            session.advance_state(InterviewState.COMPLETED)

            logger.info("session=%s Interview COMPLETED successfully", session_id)
            return InterviewResponse(
                sessionId=session_id,
                message=concluding_msg,
                feedback=feedback_obj,
            )

        # -----------------------------------------------------------------------
        # Phase 2: Normal conversation turn
        # -----------------------------------------------------------------------
        reply_msg, _ = llm_service.generate_interview_response(
            system_prompt=system_prompt,
            history=session.history,
            is_final_turn=False,
        )

        session.add_message("assistant", reply_msg)

        logger.info(
            "session=%s Reply generated, awaiting next candidate message",
            session_id,
        )
        return InterviewResponse(sessionId=session_id, message=reply_msg)


# ---------------------------------------------------------------------------
# Health & observability routes
# ---------------------------------------------------------------------------


@app.get(
    "/api/health",
    summary="Health check",
    description="Returns service health status and number of active sessions.",
)
def health_check() -> Dict[str, Any]:
    return {
        "status": "healthy",
        "service": "AI Cohort Interview Agent",
        "version": "1.0.0",
        "sessions_active": session_manager.active_count,
    }


@app.get(
    "/api/session/{session_id}",
    summary="Session metadata",
    description="Returns the current state and metadata for a given session ID.",
)
def get_session_metadata(session_id: str) -> Dict[str, Any]:
    session = session_manager.get_session(session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found.",
        )
    with session.lock:
        return session.to_metadata_dict()


@app.get(
    "/api/sessions",
    summary="List all sessions",
    description="Returns metadata snapshots for all active sessions.",
)
def list_sessions() -> Dict[str, Any]:
    return {
        "total": session_manager.active_count,
        "sessions": session_manager.list_sessions(),
    }
