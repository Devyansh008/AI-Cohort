"""
app/state/session.py

Thread-safe, in-memory session state management for the AI Interview Agent.

Architecture:
- InterviewSession  : Encapsulates all per-session state with a per-session RLock.
- SessionManager    : Global singleton registry for all active sessions.
                      Uses its own RLock to protect the sessions dictionary.

State Machine:
    GREETING → INTERVIEW → FEEDBACK_COMPILE → COMPLETED

Usage:
    from app.state.session import session_manager   # global singleton

    session = session_manager.create_session(session_id, candidate)
    session = session_manager.get_session(session_id)
    session_manager.delete_session(session_id)
"""

from __future__ import annotations

import logging
import threading
import time
from enum import Enum
from typing import Dict, List, Optional, Set

from app.api.schemas import Candidate

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# State Enum
# ---------------------------------------------------------------------------


class InterviewState(str, Enum):
    """Explicit state labels for the interview lifecycle state machine."""

    GREETING = "GREETING"
    INTERVIEW = "INTERVIEW"
    FEEDBACK_COMPILE = "FEEDBACK_COMPILE"
    COMPLETED = "COMPLETED"


# ---------------------------------------------------------------------------
# Per-Session Object
# ---------------------------------------------------------------------------


class InterviewSession:
    """
    Encapsulates all mutable state for a single interview session.

    Thread-safety:
        All state mutations should be performed inside a `with session.lock:` block.
        The lock is a re-entrant lock (RLock) so the same thread can acquire it
        multiple times without deadlocking (e.g., helper methods calling each other).
    """

    def __init__(self, session_id: str, candidate: Candidate) -> None:
        self.session_id: str = session_id
        self.candidate: Candidate = candidate

        # Conversation history in OpenAI message format: [{"role": ..., "content": ...}]
        self.history: List[Dict[str, str]] = []

        # State machine
        self.state: InterviewState = InterviewState.GREETING

        # Metrics
        self.question_count: int = 0               # total questions asked by the agent
        self.days_discussed: Set[int] = set()      # curriculum day numbers covered so far

        # Timestamps for observability
        self.created_at: float = time.time()
        self.last_active_at: float = time.time()

        # Per-session re-entrant lock
        self.lock: threading.RLock = threading.RLock()

    # ------------------------------------------------------------------
    # Convenience accessors (must be called inside lock context)
    # ------------------------------------------------------------------

    def touch(self) -> None:
        """Update last-active timestamp. Call this after every state mutation."""
        self.last_active_at = time.time()

    def add_message(self, role: str, content: str) -> None:
        """Append a message to the conversation history."""
        self.history.append({"role": role, "content": content})
        self.touch()

    def advance_state(self, new_state: InterviewState) -> None:
        """Transition to a new state with structured logging."""
        old_state = self.state
        self.state = new_state
        logger.info(
            "session=%s state_transition from=%s to=%s",
            self.session_id,
            old_state.value,
            new_state.value,
        )
        self.touch()

    @property
    def is_completed(self) -> bool:
        return self.state == InterviewState.COMPLETED

    @property
    def meets_completion_criteria(self) -> bool:
        """Check if minimum interview requirements have been fulfilled."""
        return self.question_count >= 8 and len(self.days_discussed) >= 4

    def to_metadata_dict(self) -> Dict:
        """Return a JSON-serialisable snapshot of this session's metadata."""
        return {
            "sessionId": self.session_id,
            "state": self.state.value,
            "questionCount": self.question_count,
            "daysCovered": sorted(self.days_discussed),
            "daysCoveredCount": len(self.days_discussed),
            "meetsCompletionCriteria": self.meets_completion_criteria,
            "candidate": {
                "name": self.candidate.member.name,
                "jobRole": self.candidate.member.jobRole,
            },
            "createdAt": self.created_at,
            "lastActiveAt": self.last_active_at,
        }


# ---------------------------------------------------------------------------
# Global Session Registry
# ---------------------------------------------------------------------------


class SessionManager:
    """
    Thread-safe global registry for all active InterviewSession objects.

    Implemented as a module-level singleton (see `session_manager` below).

    Design notes:
    - Uses an RLock on the registry dict to protect concurrent creates/reads/deletes.
    - Each session has its own RLock for fine-grained state mutation.
    - Sessions are kept in memory for the lifetime of the process. In production,
      swap the dict for a Redis backend to support multi-process deployments.
    """

    def __init__(self) -> None:
        self._sessions: Dict[str, InterviewSession] = {}
        self._lock: threading.RLock = threading.RLock()

    # ------------------------------------------------------------------
    # CRUD operations
    # ------------------------------------------------------------------

    def create_session(self, session_id: str, candidate: Candidate) -> InterviewSession:
        """
        Create and register a new session.

        Raises:
            ValueError: If a session with the given ID already exists.
        """
        with self._lock:
            if session_id in self._sessions:
                raise ValueError(
                    f"Session '{session_id}' already exists. "
                    "Use get_session() to retrieve it or delete it first."
                )
            session = InterviewSession(session_id, candidate)
            self._sessions[session_id] = session
            logger.info(
                "session=%s created candidate=%s",
                session_id,
                candidate.member.name,
            )
            return session

    def get_session(self, session_id: str) -> Optional[InterviewSession]:
        """Return the session if it exists, otherwise None."""
        with self._lock:
            return self._sessions.get(session_id)

    def delete_session(self, session_id: str) -> bool:
        """
        Remove a session from the registry.

        Returns:
            True if the session was found and deleted, False otherwise.
        """
        with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
                logger.info("session=%s deleted", session_id)
                return True
            return False

    def list_sessions(self) -> List[Dict]:
        """Return metadata snapshots for all active sessions."""
        with self._lock:
            return [s.to_metadata_dict() for s in self._sessions.values()]

    @property
    def active_count(self) -> int:
        """Number of sessions currently registered."""
        with self._lock:
            return len(self._sessions)


# ---------------------------------------------------------------------------
# Module-level singleton — import this in other modules
# ---------------------------------------------------------------------------

session_manager = SessionManager()
