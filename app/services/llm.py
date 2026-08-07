"""
app/services/llm.py

OpenAI GPT-4o LLM Orchestration Service for the AI Interview Agent.

Responsibilities:
  1. Manage the OpenAI client connection using environment credentials.
  2. Dual execution routes:
       - Normal conversation turns → standard chat completions (text response).
       - Final evaluation turn    → structured beta parse with Feedback schema.
  3. Retry logic with exponential backoff (up to 3 attempts).
  4. Context window management — prune history to last N messages.
  5. Graceful fallback on timeout or unrecoverable API error.

Usage:
    from app.services.llm import llm_service  # singleton

    msg, feedback = llm_service.generate_interview_response(
        system_prompt=prompt,
        history=session.history,
        is_final_turn=False,
    )
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, List, Optional, Tuple

from openai import APIConnectionError, APITimeoutError, OpenAI, RateLimitError
from openai.types.chat import ChatCompletion

from app.api.schemas import Feedback

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MAX_HISTORY_MESSAGES = 20    # prune rolling context to this many messages
_RETRY_ATTEMPTS = 3           # number of retry attempts on transient failures
_RETRY_BASE_DELAY = 1.5       # initial backoff delay in seconds (doubles each attempt)

_FALLBACK_MESSAGE = (
    "I apologise — I'm experiencing a temporary connectivity issue with the AI service. "
    "Please resend your last message and we'll pick up right where we left off."
)

_FINAL_TURN_INJECTION = (
    "The interview is now complete. You have gathered sufficient signal across multiple "
    "curriculum days. Please now output the comprehensive, structured candidate evaluation "
    "feedback object matching the Feedback schema exactly. Be specific, cite curriculum days "
    "by number and name, and make each strength, gap, and next step actionable."
)


# ---------------------------------------------------------------------------
# LLMService
# ---------------------------------------------------------------------------


class LLMService:
    """
    Orchestrates all LLM API calls for the interview agent.

    Instantiated once at application startup as a module-level singleton.
    The underlying OpenAI client is thread-safe for concurrent requests.

    Client creation is lazy — the OpenAI client object is only created on the
    first actual API call, so that test imports succeed without a live API key.
    """

    def __init__(self) -> None:
        self.model: str = os.getenv("GROQ_MODEL", "llama3-70b-8192")
        self._client: Optional[OpenAI] = None  # lazy init
        logger.info("LLMService initialised with model=%s (client lazy)", self.model)

    @property
    def client(self) -> OpenAI:
        """Return (and lazily create) the OpenAI client (configured for Groq)."""
        if self._client is None:
            api_key = os.getenv("GROQ_API_KEY", "")
            if not api_key or api_key == "gsk_your-actual-groq-key-here":
                logger.warning(
                    "GROQ_API_KEY is not set or is a placeholder. "
                    "LLM calls will fail until a valid key is provided."
                )
            self._client = OpenAI(
                api_key=api_key or "placeholder",
                base_url=os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1"),
                timeout=30.0,
                max_retries=0,
            )
        return self._client

    # ------------------------------------------------------------------
    # Context pruning
    # ------------------------------------------------------------------

    @staticmethod
    def _prune_history(history: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """
        Return only the last `_MAX_HISTORY_MESSAGES` messages from history
        to prevent context window bloat on long sessions.

        Always preserve conversation pairs (user + assistant) to avoid
        orphaned roles at the start of the pruned list.
        """
        if len(history) <= _MAX_HISTORY_MESSAGES:
            return history
        pruned = history[-_MAX_HISTORY_MESSAGES:]
        # Ensure we don't start with an assistant message (OpenAI may reject)
        while pruned and pruned[0]["role"] == "assistant":
            pruned = pruned[1:]
        logger.debug(
            "History pruned from %d to %d messages", len(history), len(pruned)
        )
        return pruned

    # ------------------------------------------------------------------
    # Retry wrapper
    # ------------------------------------------------------------------

    def _call_with_retry(self, call_fn, *args, **kwargs) -> Any:
        """
        Execute `call_fn(*args, **kwargs)` with exponential backoff retry
        on transient OpenAI errors (rate limits, timeouts, connection errors).

        Raises the last exception if all attempts are exhausted.
        """
        last_exc: Optional[Exception] = None
        delay = _RETRY_BASE_DELAY

        for attempt in range(1, _RETRY_ATTEMPTS + 1):
            try:
                return call_fn(*args, **kwargs)
            except RateLimitError as exc:
                logger.warning(
                    "RateLimitError on attempt %d/%d — retrying in %.1fs",
                    attempt, _RETRY_ATTEMPTS, delay,
                )
                last_exc = exc
            except APITimeoutError as exc:
                logger.warning(
                    "APITimeoutError on attempt %d/%d — retrying in %.1fs",
                    attempt, _RETRY_ATTEMPTS, delay,
                )
                last_exc = exc
            except APIConnectionError as exc:
                logger.warning(
                    "APIConnectionError on attempt %d/%d — retrying in %.1fs",
                    attempt, _RETRY_ATTEMPTS, delay,
                )
                last_exc = exc

            if attempt < _RETRY_ATTEMPTS:
                time.sleep(delay)
                delay *= 2  # exponential backoff

        logger.error(
            "All %d retry attempts exhausted. Last error: %s",
            _RETRY_ATTEMPTS, last_exc,
        )
        raise last_exc  # type: ignore[misc]

    # ------------------------------------------------------------------
    # Core generation methods
    # ------------------------------------------------------------------

    def _generate_text_response(
        self,
        messages: List[Dict[str, str]],
    ) -> str:
        """Standard chat completions call — returns plain text."""
        response: ChatCompletion = self._call_with_retry(
            self.client.chat.completions.create,
            model=self.model,
            messages=messages,
            temperature=0.7,
            max_tokens=1024,
        )
        content = response.choices[0].message.content
        logger.info(
            "Text response generated: tokens_used=%d",
            response.usage.total_tokens if response.usage else -1,
        )
        return content.strip() if content else _FALLBACK_MESSAGE

    def _generate_structured_feedback(
        self,
        messages: List[Dict[str, str]],
    ) -> Tuple[str, Feedback]:
        """
        Structured output call using the beta parse API.
        Forces the LLM to output a JSON object matching the Feedback Pydantic schema.
        Returns a tuple of (closing_message, Feedback).
        """
        # Inject the final evaluation instruction into the message sequence
        final_messages = messages + [
            {"role": "user", "content": _FINAL_TURN_INJECTION}
        ]

        response = self._call_with_retry(
            self.client.beta.chat.completions.parse,
            model=self.model,
            messages=final_messages,
            response_format=Feedback,
            temperature=0.3,   # lower temp for deterministic structured output
        )

        parsed_feedback: Feedback = response.choices[0].message.parsed

        if parsed_feedback is None:
            # Fallback: extract raw JSON and parse manually
            raw = response.choices[0].message.content or "{}"
            parsed_feedback = Feedback.model_validate_json(raw)

        logger.info(
            "Structured feedback compiled: strengths=%d, gaps=%d, next=%d",
            len(parsed_feedback.strengths),
            len(parsed_feedback.gaps),
            len(parsed_feedback.next),
        )

        concluding_message = (
            "Thank you for taking the time to share your AI Cohort journey with me. "
            "That concludes our technical interview. Here is your structured readiness "
            "evaluation and personalised recommendations."
        )
        return concluding_message, parsed_feedback

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def generate_interview_response(
        self,
        system_prompt: str,
        history: List[Dict[str, str]],
        is_final_turn: bool = False,
    ) -> Tuple[str, Optional[Feedback]]:
        """
        Generate the next interview agent response.

        Args:
            system_prompt: The assembled system prompt from PromptBuilder.
            history:       The current conversation history (list of role/content dicts).
            is_final_turn: If True, invoke structured output parsing for Feedback.

        Returns:
            A tuple of:
              - message (str): The agent's next message to send to the candidate.
              - feedback (Optional[Feedback]): Populated only when is_final_turn=True.

        Raises:
            RuntimeError: On unrecoverable API failure after all retry attempts.
        """
        # Build full message list: [system] + pruned_history
        pruned = self._prune_history(history)
        messages: List[Dict[str, str]] = [
            {"role": "system", "content": system_prompt},
            *pruned,
        ]

        try:
            if is_final_turn:
                logger.info("Invoking structured Feedback parse (final turn)")
                msg, feedback = self._generate_structured_feedback(messages)
                return msg, feedback
            else:
                logger.info("Invoking standard text generation (conversation turn)")
                msg = self._generate_text_response(messages)
                return msg, None

        except Exception as exc:
            logger.error("Unrecoverable LLM error: %s", exc, exc_info=True)
            # Return graceful fallback so the HTTP endpoint doesn't 500 the client
            if is_final_turn:
                fallback_feedback = Feedback(
                    summary="Unable to compile feedback due to a service interruption. Please try again.",
                    strengths=["Interview completed successfully"],
                    gaps=["Feedback compilation was interrupted"],
                    next=["Please restart the feedback generation by contacting support"],
                )
                return _FALLBACK_MESSAGE, fallback_feedback
            return _FALLBACK_MESSAGE, None


# ---------------------------------------------------------------------------
# Module-level singleton — import this in other modules
# ---------------------------------------------------------------------------

llm_service = LLMService()
