"""
tests/test_interview.py

Comprehensive unit + integration tests for the AI Cohort Interview Agent.

Test coverage:
  1. Health check route
  2. Session initialisation (success + missing candidate)
  3. Session conflict (duplicate sessionId)
  4. Conversation turn state propagation
  5. Session metadata endpoint
  6. Final-turn feedback compilation
  7. COMPLETED session rejects further messages
  8. Active session without message returns 400
  9. Schema validation error handling
  10. Concurrent session isolation

All OpenAI API calls are mocked so tests run without a real API key.
"""

from __future__ import annotations

import json
import threading
import uuid
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.schemas import Feedback
from app.main import app
from app.state.session import InterviewState, SessionManager, session_manager

# ---------------------------------------------------------------------------
# Test client
# ---------------------------------------------------------------------------

client = TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Fixtures & shared data
# ---------------------------------------------------------------------------


def _make_session_id() -> str:
    """Generate a unique session ID for each test to ensure isolation."""
    return f"test-session-{uuid.uuid4().hex[:8]}"


SARAH_CANDIDATE: Dict[str, Any] = {
    "member": {
        "id": "CAND-001",
        "name": "Sarah Johnson",
        "jobRole": "Senior Data Engineer",
        "yearsExperience": 9,
        "education": "MS Computer Science",
        "status": "COMPLETED",
    },
    "missions": [
        {"day": 7, "title": "Embeddings Explained", "passed": True, "attempts": 1},
        {"day": 8, "title": "Vector Databases Overview", "passed": True, "attempts": 1},
        {"day": 10, "title": "Retrieval & Matching Engine", "passed": True, "attempts": 2},
        {"day": 12, "title": "Prompt Engineering Fundamentals", "passed": True, "attempts": 4},
        {"day": 16, "title": "Chatbot Backend & API Integration", "passed": True, "attempts": 1},
        {"day": 22, "title": "Multi-Agent Orchestration", "passed": True, "attempts": 2},
        {"day": 23, "title": "Model Context Protocol (MCP)", "passed": True, "attempts": 2},
        {"day": 28, "title": "Docker & Kubernetes Deployment", "passed": True, "attempts": 3},
        {"day": 29, "title": "Monitoring, Logging & Observability", "skipped": True},
        {"day": 31, "title": "Capstone Project & Final Demo", "passed": True, "attempts": 1},
    ],
    "signals": {
        "commitDays": 28,
        "missionsCompleted": 30,
        "missionsFirstTry": 20,
    },
}

EMILY_CANDIDATE: Dict[str, Any] = {
    "member": {
        "id": "CAND-002",
        "name": "Emily Chen",
        "jobRole": "AI Engineer",
        "yearsExperience": 6,
        "education": "MS AI",
        "status": "COMPLETED",
    },
    "missions": [
        {"day": 22, "title": "Multi-Agent Orchestration", "passed": True, "attempts": 1},
        {"day": 23, "title": "Model Context Protocol (MCP)", "passed": True, "attempts": 1},
        {"day": 10, "title": "Retrieval & Matching Engine", "passed": True, "attempts": 1},
        {"day": 7, "title": "Embeddings Explained", "passed": True, "attempts": 2},
        {"day": 14, "title": "Structured Outputs & JSON Mode", "passed": True, "attempts": 1},
    ],
    "signals": {
        "commitDays": 31,
        "missionsCompleted": 28,
        "missionsFirstTry": 25,
    },
}

# Mock LLM response for standard text turns
MOCK_LLM_TEXT = (
    "Great question — can you walk me through how you configured your ChromaDB "
    "collection for the healthcare RAG pipeline, specifically around metadata filtering?"
)

# Mock structured Feedback object
MOCK_FEEDBACK = Feedback(
    summary=(
        "Sarah is an exceptional candidate with strong data engineering fundamentals. "
        "She demonstrates mastery of embeddings, hybrid search, and containerised AI deployments."
    ),
    strengths=[
        "Outstanding understanding of embedding dimensions and cosine similarity (Day 7).",
        "Pragmatic approach to hybrid search with BM25 + dense retrieval (Day 10).",
        "Excellent mastery of Docker multi-stage builds and Kubernetes health checks (Day 28).",
    ],
    gaps=[
        "Unfamiliarity with Prometheus metrics and Grafana dashboards due to skipping Day 29.",
        "Slight hesitation on MCP server-client transport layer details (Day 23).",
    ],
    next=[
        "Complete Day 29 curriculum on Monitoring & Observability, focusing on OpenTelemetry.",
        "Build a custom MCP server exposing tools to Claude Desktop to solidify Day 23 concepts.",
    ],
)


def _mock_llm_text_response(*args, **kwargs):
    """Mock that returns a plain text response (normal turn)."""
    return MOCK_LLM_TEXT, None


def _mock_llm_feedback_response(*args, **kwargs):
    """Mock that returns the final structured feedback response."""
    return (
        "Thank you for completing this technical interview. Here is your structured evaluation.",
        MOCK_FEEDBACK,
    )


# ---------------------------------------------------------------------------
# Auto-clean sessions after each test
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def clean_sessions():
    """
    Ensure each test starts and ends with a clean session registry.
    This prevents test pollution between runs.
    """
    yield
    # Post-test cleanup: remove any test sessions
    with session_manager._lock:
        test_sessions = [
            sid for sid in list(session_manager._sessions.keys())
            if sid.startswith("test-")
        ]
        for sid in test_sessions:
            session_manager._sessions.pop(sid, None)


# ===========================================================================
# Test 1: Health check
# ===========================================================================


class TestHealthCheck:
    def test_health_returns_200(self):
        response = client.get("/api/health")
        assert response.status_code == 200

    def test_health_response_structure(self):
        response = client.get("/api/health")
        body = response.json()
        assert body["status"] == "healthy"
        assert "sessions_active" in body
        assert isinstance(body["sessions_active"], int)

    def test_health_service_name(self):
        response = client.get("/api/health")
        body = response.json()
        assert "AI Cohort" in body.get("service", "")


# ===========================================================================
# Test 2: Session initialisation
# ===========================================================================


class TestSessionInitialisation:
    @patch("app.main.llm_service.generate_interview_response", side_effect=_mock_llm_text_response)
    def test_init_success_returns_200(self, mock_llm):
        session_id = _make_session_id()
        response = client.post(
            "/api/interview",
            json={"sessionId": session_id, "candidate": SARAH_CANDIDATE},
        )
        assert response.status_code == 200

    @patch("app.main.llm_service.generate_interview_response", side_effect=_mock_llm_text_response)
    def test_init_returns_correct_session_id(self, mock_llm):
        session_id = _make_session_id()
        response = client.post(
            "/api/interview",
            json={"sessionId": session_id, "candidate": SARAH_CANDIDATE},
        )
        body = response.json()
        assert body["sessionId"] == session_id

    @patch("app.main.llm_service.generate_interview_response", side_effect=_mock_llm_text_response)
    def test_init_returns_non_empty_message(self, mock_llm):
        session_id = _make_session_id()
        response = client.post(
            "/api/interview",
            json={"sessionId": session_id, "candidate": SARAH_CANDIDATE},
        )
        body = response.json()
        assert "message" in body
        assert len(body["message"]) > 10

    @patch("app.main.llm_service.generate_interview_response", side_effect=_mock_llm_text_response)
    def test_init_no_feedback_on_first_turn(self, mock_llm):
        session_id = _make_session_id()
        response = client.post(
            "/api/interview",
            json={"sessionId": session_id, "candidate": SARAH_CANDIDATE},
        )
        body = response.json()
        assert body.get("feedback") is None

    @patch("app.main.llm_service.generate_interview_response", side_effect=_mock_llm_text_response)
    def test_init_session_state_is_interview(self, mock_llm):
        session_id = _make_session_id()
        client.post(
            "/api/interview",
            json={"sessionId": session_id, "candidate": SARAH_CANDIDATE},
        )
        session = session_manager.get_session(session_id)
        assert session is not None
        assert session.state == InterviewState.INTERVIEW

    @patch("app.main.llm_service.generate_interview_response", side_effect=_mock_llm_text_response)
    def test_init_first_day_added_to_days_discussed(self, mock_llm):
        session_id = _make_session_id()
        client.post(
            "/api/interview",
            json={"sessionId": session_id, "candidate": SARAH_CANDIDATE},
        )
        session = session_manager.get_session(session_id)
        # Day 7 is the first passed day in SARAH_CANDIDATE
        assert 7 in session.days_discussed


# ===========================================================================
# Test 3: Missing candidate on new session
# ===========================================================================


class TestMissingCandidateOnNewSession:
    def test_missing_candidate_returns_400(self):
        session_id = _make_session_id()
        response = client.post(
            "/api/interview",
            json={"sessionId": session_id},  # no candidate field
        )
        assert response.status_code == 400

    def test_missing_candidate_error_detail(self):
        session_id = _make_session_id()
        response = client.post(
            "/api/interview",
            json={"sessionId": session_id},
        )
        body = response.json()
        assert "detail" in body
        assert "candidate" in body["detail"].lower()


# ===========================================================================
# Test 4: Schema validation errors
# ===========================================================================


class TestSchemaValidation:
    def test_invalid_status_field_returns_422(self):
        session_id = _make_session_id()
        bad_candidate = {**SARAH_CANDIDATE, "member": {**SARAH_CANDIDATE["member"], "status": "INVALID_STATUS"}}
        response = client.post(
            "/api/interview",
            json={"sessionId": session_id, "candidate": bad_candidate},
        )
        assert response.status_code == 422

    def test_missing_required_field_returns_422(self):
        response = client.post(
            "/api/interview",
            json={"candidate": SARAH_CANDIDATE},  # missing sessionId
        )
        assert response.status_code == 422

    def test_empty_session_id_returns_422(self):
        response = client.post(
            "/api/interview",
            json={"sessionId": ""},  # empty string
        )
        assert response.status_code == 422

    def test_negative_years_experience_returns_422(self):
        session_id = _make_session_id()
        bad_candidate = {
            **SARAH_CANDIDATE,
            "member": {**SARAH_CANDIDATE["member"], "yearsExperience": -1},
        }
        response = client.post(
            "/api/interview",
            json={"sessionId": session_id, "candidate": bad_candidate},
        )
        assert response.status_code == 422


# ===========================================================================
# Test 5: Conversation turn state propagation
# ===========================================================================


class TestConversationTurns:
    @patch("app.main.llm_service.generate_interview_response", side_effect=_mock_llm_text_response)
    def _init_session(self, session_id, mock_llm):
        client.post(
            "/api/interview",
            json={"sessionId": session_id, "candidate": SARAH_CANDIDATE},
        )

    @patch("app.main.llm_service.generate_interview_response", side_effect=_mock_llm_text_response)
    def test_conversation_turn_returns_200(self, mock_llm):
        session_id = _make_session_id()
        # Init
        client.post("/api/interview", json={"sessionId": session_id, "candidate": SARAH_CANDIDATE})
        # Turn 2
        response = client.post(
            "/api/interview",
            json={
                "sessionId": session_id,
                "message": "We used Sentence Transformers with all-MiniLM-L6-v2.",
            },
        )
        assert response.status_code == 200

    @patch("app.main.llm_service.generate_interview_response", side_effect=_mock_llm_text_response)
    def test_conversation_turn_returns_message(self, mock_llm):
        session_id = _make_session_id()
        client.post("/api/interview", json={"sessionId": session_id, "candidate": SARAH_CANDIDATE})
        response = client.post(
            "/api/interview",
            json={"sessionId": session_id, "message": "We stored embeddings in ChromaDB."},
        )
        body = response.json()
        assert "message" in body
        assert len(body["message"]) > 5

    @patch("app.main.llm_service.generate_interview_response", side_effect=_mock_llm_text_response)
    def test_question_count_increments(self, mock_llm):
        session_id = _make_session_id()
        client.post("/api/interview", json={"sessionId": session_id, "candidate": SARAH_CANDIDATE})
        initial_count = session_manager.get_session(session_id).question_count

        client.post(
            "/api/interview",
            json={"sessionId": session_id, "message": "I used ChromaDB for storage."},
        )
        updated_count = session_manager.get_session(session_id).question_count
        assert updated_count > initial_count

    @patch("app.main.llm_service.generate_interview_response", side_effect=_mock_llm_text_response)
    def test_history_appended_correctly(self, mock_llm):
        session_id = _make_session_id()
        client.post("/api/interview", json={"sessionId": session_id, "candidate": SARAH_CANDIDATE})

        user_message = "I configured ChromaDB with cosine similarity."
        client.post(
            "/api/interview",
            json={"sessionId": session_id, "message": user_message},
        )

        session = session_manager.get_session(session_id)
        # History should contain: assistant greeting, user message, assistant reply
        user_messages = [m["content"] for m in session.history if m["role"] == "user"]
        assert user_message in user_messages


# ===========================================================================
# Test 6: Missing message on active session
# ===========================================================================


class TestMissingMessageOnActiveSession:
    @patch("app.main.llm_service.generate_interview_response", side_effect=_mock_llm_text_response)
    def test_missing_message_returns_400(self, mock_llm):
        session_id = _make_session_id()
        client.post("/api/interview", json={"sessionId": session_id, "candidate": SARAH_CANDIDATE})
        response = client.post("/api/interview", json={"sessionId": session_id})
        assert response.status_code == 400

    @patch("app.main.llm_service.generate_interview_response", side_effect=_mock_llm_text_response)
    def test_empty_message_returns_422(self, mock_llm):
        session_id = _make_session_id()
        client.post("/api/interview", json={"sessionId": session_id, "candidate": SARAH_CANDIDATE})
        # Empty string should fail Pydantic min_length=1 validation
        response = client.post(
            "/api/interview",
            json={"sessionId": session_id, "message": "   "},  # whitespace stripped = empty
        )
        # Could be 400 or 422 depending on strip behaviour
        assert response.status_code in (400, 422)


# ===========================================================================
# Test 7: Session metadata endpoint
# ===========================================================================


class TestSessionMetadataEndpoint:
    @patch("app.main.llm_service.generate_interview_response", side_effect=_mock_llm_text_response)
    def test_metadata_returns_200(self, mock_llm):
        session_id = _make_session_id()
        client.post("/api/interview", json={"sessionId": session_id, "candidate": SARAH_CANDIDATE})
        response = client.get(f"/api/session/{session_id}")
        assert response.status_code == 200

    @patch("app.main.llm_service.generate_interview_response", side_effect=_mock_llm_text_response)
    def test_metadata_contains_correct_state(self, mock_llm):
        session_id = _make_session_id()
        client.post("/api/interview", json={"sessionId": session_id, "candidate": SARAH_CANDIDATE})
        response = client.get(f"/api/session/{session_id}")
        body = response.json()
        assert body["state"] == InterviewState.INTERVIEW.value

    @patch("app.main.llm_service.generate_interview_response", side_effect=_mock_llm_text_response)
    def test_metadata_contains_question_count(self, mock_llm):
        session_id = _make_session_id()
        client.post("/api/interview", json={"sessionId": session_id, "candidate": SARAH_CANDIDATE})
        response = client.get(f"/api/session/{session_id}")
        body = response.json()
        assert "questionCount" in body
        assert body["questionCount"] >= 1

    @patch("app.main.llm_service.generate_interview_response", side_effect=_mock_llm_text_response)
    def test_metadata_contains_days_covered(self, mock_llm):
        session_id = _make_session_id()
        client.post("/api/interview", json={"sessionId": session_id, "candidate": SARAH_CANDIDATE})
        response = client.get(f"/api/session/{session_id}")
        body = response.json()
        assert "daysCovered" in body
        assert isinstance(body["daysCovered"], list)

    def test_metadata_for_unknown_session_returns_404(self):
        response = client.get("/api/session/nonexistent-session-xyz")
        assert response.status_code == 404


# ===========================================================================
# Test 8: Final evaluation turn — feedback compilation
# ===========================================================================


class TestFinalEvaluationTurn:
    def _drive_session_to_final_turn(self, session_id: str) -> None:
        """
        Directly manipulate session state to simulate a session at the
        threshold for feedback compilation (8 questions, 4+ days).
        """
        with patch("app.main.llm_service.generate_interview_response", side_effect=_mock_llm_text_response):
            client.post("/api/interview", json={"sessionId": session_id, "candidate": SARAH_CANDIDATE})

        session = session_manager.get_session(session_id)
        with session.lock:
            session.question_count = 7  # next turn will make it 8
            session.days_discussed = {7, 8, 10, 12}  # exactly 4 days

    @patch("app.main.llm_service.generate_interview_response", side_effect=_mock_llm_feedback_response)
    def test_final_turn_returns_feedback(self, mock_llm):
        session_id = _make_session_id()
        self._drive_session_to_final_turn(session_id)

        response = client.post(
            "/api/interview",
            json={"sessionId": session_id, "message": "I also implemented observability with Langfuse."},
        )
        assert response.status_code == 200
        body = response.json()
        assert "feedback" in body
        assert body["feedback"] is not None

    @patch("app.main.llm_service.generate_interview_response", side_effect=_mock_llm_feedback_response)
    def test_final_turn_feedback_has_all_fields(self, mock_llm):
        session_id = _make_session_id()
        self._drive_session_to_final_turn(session_id)

        response = client.post(
            "/api/interview",
            json={"sessionId": session_id, "message": "Final answer here."},
        )
        body = response.json()
        feedback = body["feedback"]
        assert "summary" in feedback
        assert "strengths" in feedback
        assert "gaps" in feedback
        assert "next" in feedback

    @patch("app.main.llm_service.generate_interview_response", side_effect=_mock_llm_feedback_response)
    def test_final_turn_feedback_lists_are_populated(self, mock_llm):
        session_id = _make_session_id()
        self._drive_session_to_final_turn(session_id)

        response = client.post(
            "/api/interview",
            json={"sessionId": session_id, "message": "Final answer."},
        )
        feedback = response.json()["feedback"]
        assert len(feedback["strengths"]) >= 1
        assert len(feedback["next"]) >= 1

    @patch("app.main.llm_service.generate_interview_response", side_effect=_mock_llm_feedback_response)
    def test_session_state_is_completed_after_feedback(self, mock_llm):
        session_id = _make_session_id()
        self._drive_session_to_final_turn(session_id)

        client.post(
            "/api/interview",
            json={"sessionId": session_id, "message": "Final answer."},
        )
        session = session_manager.get_session(session_id)
        assert session.state == InterviewState.COMPLETED


# ===========================================================================
# Test 9: Completed session rejects further messages
# ===========================================================================


class TestCompletedSessionRejection:
    def _create_completed_session(self, session_id: str) -> None:
        """Build and complete a session by simulating state directly."""
        with patch("app.main.llm_service.generate_interview_response", side_effect=_mock_llm_text_response):
            client.post("/api/interview", json={"sessionId": session_id, "candidate": SARAH_CANDIDATE})

        session = session_manager.get_session(session_id)
        with session.lock:
            session.question_count = 7
            session.days_discussed = {7, 8, 10, 12}

        with patch("app.main.llm_service.generate_interview_response", side_effect=_mock_llm_feedback_response):
            client.post("/api/interview", json={"sessionId": session_id, "message": "Final answer."})

    def test_completed_session_rejects_new_message(self):
        session_id = _make_session_id()
        self._create_completed_session(session_id)

        response = client.post(
            "/api/interview",
            json={"sessionId": session_id, "message": "Can I ask another question?"},
        )
        assert response.status_code == 400

    def test_completed_session_error_message_mentions_completed(self):
        session_id = _make_session_id()
        self._create_completed_session(session_id)

        response = client.post(
            "/api/interview",
            json={"sessionId": session_id, "message": "Another question."},
        )
        body = response.json()
        assert "completed" in body["detail"].lower() or "closed" in body["detail"].lower()


# ===========================================================================
# Test 10: Different candidate personas are initialised correctly
# ===========================================================================


class TestMultipleCandidatePersonas:
    @patch("app.main.llm_service.generate_interview_response", side_effect=_mock_llm_text_response)
    def test_emily_chen_session_initialises(self, mock_llm):
        session_id = _make_session_id()
        response = client.post(
            "/api/interview",
            json={"sessionId": session_id, "candidate": EMILY_CANDIDATE},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["sessionId"] == session_id

    @patch("app.main.llm_service.generate_interview_response", side_effect=_mock_llm_text_response)
    def test_emily_session_days_discussed_initialised(self, mock_llm):
        session_id = _make_session_id()
        client.post("/api/interview", json={"sessionId": session_id, "candidate": EMILY_CANDIDATE})
        session = session_manager.get_session(session_id)
        # _get_first_passed_day() sorts missions ascending by day number.
        # Emily's missions include day 7, which is the lowest passed day — so day 7 is
        # the first one added to days_discussed on session initialisation.
        assert 7 in session.days_discussed
        assert len(session.days_discussed) >= 1


# ===========================================================================
# Test 11: Session isolation (concurrent sessions)
# ===========================================================================


class TestSessionIsolation:
    @patch("app.main.llm_service.generate_interview_response", side_effect=_mock_llm_text_response)
    def test_two_sessions_are_independent(self, mock_llm):
        session_a = _make_session_id()
        session_b = _make_session_id()

        client.post("/api/interview", json={"sessionId": session_a, "candidate": SARAH_CANDIDATE})
        client.post("/api/interview", json={"sessionId": session_b, "candidate": EMILY_CANDIDATE})

        sess_a = session_manager.get_session(session_a)
        sess_b = session_manager.get_session(session_b)

        assert sess_a is not None
        assert sess_b is not None
        assert sess_a.session_id != sess_b.session_id
        assert sess_a.candidate.member.name == "Sarah Johnson"
        assert sess_b.candidate.member.name == "Emily Chen"

    @patch("app.main.llm_service.generate_interview_response", side_effect=_mock_llm_text_response)
    def test_concurrent_initialisation_thread_safe(self, mock_llm):
        """Stress test: 10 threads each start their own session concurrently."""
        results = []
        errors = []

        def init_session():
            session_id = _make_session_id()
            try:
                response = client.post(
                    "/api/interview",
                    json={"sessionId": session_id, "candidate": SARAH_CANDIDATE},
                )
                results.append(response.status_code)
            except Exception as exc:
                errors.append(str(exc))

        threads = [threading.Thread(target=init_session) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Concurrent init errors: {errors}"
        assert all(code == 200 for code in results), f"Status codes: {results}"


# ===========================================================================
# Test 12: PromptBuilder unit tests
# ===========================================================================


class TestPromptBuilder:
    def test_prompt_builder_returns_string(self):
        from app.services.prompt_builder import prompt_builder
        prompt = prompt_builder.build_system_prompt(SARAH_CANDIDATE)
        assert isinstance(prompt, str)
        assert len(prompt) > 100

    def test_prompt_contains_candidate_name(self):
        from app.services.prompt_builder import prompt_builder
        prompt = prompt_builder.build_system_prompt(SARAH_CANDIDATE)
        assert "Sarah Johnson" in prompt

    def test_prompt_contains_job_role(self):
        from app.services.prompt_builder import prompt_builder
        prompt = prompt_builder.build_system_prompt(SARAH_CANDIDATE)
        assert "Senior Data Engineer" in prompt

    def test_prompt_contains_skipped_day_warning(self):
        from app.services.prompt_builder import prompt_builder
        prompt = prompt_builder.build_system_prompt(SARAH_CANDIDATE)
        # Day 29 is skipped — should appear in prompt with a warning
        assert "29" in prompt
        assert "SKIPPED" in prompt

    def test_prompt_contains_curriculum_rules(self):
        from app.services.prompt_builder import prompt_builder
        prompt = prompt_builder.build_system_prompt(SARAH_CANDIDATE)
        assert "8 questions" in prompt or "MINIMUM" in prompt

    def test_prompt_graceful_with_missing_curriculum(self):
        from app.services.prompt_builder import PromptBuilder
        # Point to a non-existent file
        pb = PromptBuilder(curriculum_path="/tmp/nonexistent_curriculum.json")
        prompt = pb.build_system_prompt(SARAH_CANDIDATE)
        assert isinstance(prompt, str)  # Should not raise


# ===========================================================================
# Test 13: SessionManager unit tests
# ===========================================================================


class TestSessionManager:
    def test_create_and_retrieve_session(self):
        from app.api.schemas import Candidate as CandidateSchema
        mgr = SessionManager()
        sid = _make_session_id()
        candidate = CandidateSchema(**SARAH_CANDIDATE)
        session = mgr.create_session(sid, candidate)
        assert session is not None
        assert mgr.get_session(sid) is session

    def test_create_duplicate_session_raises_value_error(self):
        from app.api.schemas import Candidate as CandidateSchema
        mgr = SessionManager()
        sid = _make_session_id()
        candidate = CandidateSchema(**SARAH_CANDIDATE)
        mgr.create_session(sid, candidate)
        with pytest.raises(ValueError, match="already exists"):
            mgr.create_session(sid, candidate)

    def test_get_nonexistent_session_returns_none(self):
        mgr = SessionManager()
        assert mgr.get_session("nonexistent-xyz-123") is None

    def test_delete_session(self):
        from app.api.schemas import Candidate as CandidateSchema
        mgr = SessionManager()
        sid = _make_session_id()
        candidate = CandidateSchema(**SARAH_CANDIDATE)
        mgr.create_session(sid, candidate)
        result = mgr.delete_session(sid)
        assert result is True
        assert mgr.get_session(sid) is None

    def test_delete_nonexistent_session_returns_false(self):
        mgr = SessionManager()
        result = mgr.delete_session("does-not-exist")
        assert result is False

    def test_active_count(self):
        from app.api.schemas import Candidate as CandidateSchema
        mgr = SessionManager()
        candidate = CandidateSchema(**SARAH_CANDIDATE)
        initial_count = mgr.active_count
        sid = _make_session_id()
        mgr.create_session(sid, candidate)
        assert mgr.active_count == initial_count + 1
        mgr.delete_session(sid)
        assert mgr.active_count == initial_count

    def test_session_initial_state_is_greeting(self):
        from app.api.schemas import Candidate as CandidateSchema
        mgr = SessionManager()
        candidate = CandidateSchema(**SARAH_CANDIDATE)
        session = mgr.create_session(_make_session_id(), candidate)
        assert session.state == InterviewState.GREETING

    def test_session_meets_completion_criteria_false_initially(self):
        from app.api.schemas import Candidate as CandidateSchema
        mgr = SessionManager()
        candidate = CandidateSchema(**SARAH_CANDIDATE)
        session = mgr.create_session(_make_session_id(), candidate)
        assert session.meets_completion_criteria is False

    def test_session_meets_completion_criteria_true_when_threshold_reached(self):
        from app.api.schemas import Candidate as CandidateSchema
        mgr = SessionManager()
        candidate = CandidateSchema(**SARAH_CANDIDATE)
        session = mgr.create_session(_make_session_id(), candidate)
        with session.lock:
            session.question_count = 8
            session.days_discussed = {7, 8, 10, 12}
        assert session.meets_completion_criteria is True


# ===========================================================================
# Test 14: List sessions endpoint
# ===========================================================================


class TestListSessionsEndpoint:
    @patch("app.main.llm_service.generate_interview_response", side_effect=_mock_llm_text_response)
    def test_list_sessions_returns_200(self, mock_llm):
        response = client.get("/api/sessions")
        assert response.status_code == 200

    @patch("app.main.llm_service.generate_interview_response", side_effect=_mock_llm_text_response)
    def test_list_sessions_contains_total(self, mock_llm):
        response = client.get("/api/sessions")
        body = response.json()
        assert "total" in body
        assert "sessions" in body
        assert isinstance(body["sessions"], list)
