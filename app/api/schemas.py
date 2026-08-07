"""
app/api/schemas.py

Strict Pydantic v2 schemas for the AI Cohort Interview Agent API.
Covers request/response models and the structured feedback output schema
that is directly mapped to OpenAI's beta structured-output parser.
"""

from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Candidate Data Models
# ---------------------------------------------------------------------------


class Member(BaseModel):
    """Core candidate biographical profile."""

    id: str = Field(..., description="Unique candidate identifier (e.g. CAND-001)")
    name: str = Field(..., min_length=1, description="Full name of the candidate")
    jobRole: str = Field(..., description="Current professional job title")
    yearsExperience: int = Field(..., ge=0, le=60, description="Total years of professional experience")
    education: str = Field(..., description="Highest education qualification")
    status: str = Field(..., description="Cohort completion status (e.g. COMPLETED, IN_PROGRESS)")

    @field_validator("status")
    @classmethod
    def status_must_be_valid(cls, v: str) -> str:
        allowed = {"COMPLETED", "IN_PROGRESS", "DROPPED"}
        if v.upper() not in allowed:
            raise ValueError(f"status must be one of {allowed}, got '{v}'")
        return v.upper()


class Mission(BaseModel):
    """A single curriculum day / mission record from the candidate's learning path."""

    day: int = Field(..., ge=1, le=31, description="Curriculum day number (1–31)")
    title: str = Field(..., min_length=1, description="Name of the module/mission")
    passed: Optional[bool] = Field(None, description="True if the candidate passed this day")
    skipped: Optional[bool] = Field(None, description="True if the candidate explicitly skipped this day")
    attempts: Optional[int] = Field(None, ge=1, description="Number of attempts taken to pass (only if passed=True)")

    @field_validator("passed", "skipped", mode="before")
    @classmethod
    def coerce_none_bool(cls, v):  # noqa: ANN001
        return v


class Signals(BaseModel):
    """Engagement and performance signals extracted from cohort tracking data."""

    commitDays: int = Field(..., ge=0, description="Total days the candidate committed to the program")
    missionsCompleted: int = Field(..., ge=0, description="Total missions marked as completed")
    missionsFirstTry: int = Field(..., ge=0, description="Missions passed on the very first attempt")


class Candidate(BaseModel):
    """Complete candidate object combining profile, mission history, and signals."""

    member: Member
    missions: List[Mission] = Field(..., min_length=1, description="List of curriculum missions attempted")
    signals: Signals


# ---------------------------------------------------------------------------
# Request Models
# ---------------------------------------------------------------------------


class InterviewRequest(BaseModel):
    """
    Unified request body for POST /api/interview.

    - Round 1 (new session): supply `sessionId` + `candidate`. `message` is ignored.
    - Round 2+ (ongoing session): supply `sessionId` + `message`. `candidate` is ignored.
    """

    sessionId: str = Field(..., min_length=1, description="Unique identifier for this interview session")
    candidate: Optional[Candidate] = Field(
        None,
        description="Required only on the first request to initialize a new session",
    )
    message: Optional[str] = Field(
        None,
        min_length=1,
        description="Candidate's reply in ongoing conversation turns",
    )

    model_config = {"str_strip_whitespace": True}


# ---------------------------------------------------------------------------
# Response Models
# ---------------------------------------------------------------------------


class Feedback(BaseModel):
    """
    Structured evaluation feedback produced at interview completion.

    This model is used directly as the `response_format` for
    `client.beta.chat.completions.parse`, so field descriptions
    act as schema metadata for the LLM to follow.
    """

    summary: str = Field(
        ...,
        description=(
            "A 3–5 sentence professional summary of the candidate's overall technical readiness, "
            "communication quality, and cohort performance."
        ),
    )
    strengths: List[str] = Field(
        ...,
        min_length=1,
        description=(
            "A concise bullet-list of specific technical capabilities the candidate demonstrated. "
            "Each entry should cite the relevant curriculum day and concept (e.g., 'Day 7 – Embeddings')."
        ),
    )
    gaps: List[str] = Field(
        ...,
        description=(
            "Observable technical weaknesses, skipped modules, or shallow answers. "
            "Each entry should reference the relevant curriculum day or concept."
        ),
    )
    next: List[str] = Field(
        ...,
        min_length=1,
        description=(
            "Concrete, actionable next steps the candidate should take to close their knowledge gaps "
            "and advance their career. Each step should be specific, not generic."
        ),
    )


class InterviewResponse(BaseModel):
    """
    Unified response envelope for POST /api/interview.

    - Normal turns: `sessionId` + `message` only.
    - Final turn: `sessionId` + `message` + `feedback`.
    """

    sessionId: str
    message: str
    feedback: Optional[Feedback] = None
