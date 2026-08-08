"""
app/services/llm.py

Groq Llama-3 LLM Orchestration Service for the AI Interview Agent.

Responsibilities:
  1. Manage the Groq-compatible OpenAI client using GROQ_API_KEY + GROQ_BASE_URL.
  2. Dual execution routes:
       - Normal conversation turns  → standard chat.completions.create (text response).
       - Final evaluation turn      → chat.completions.create with response_format=json_object,
                                      then manually parse raw JSON into the Feedback Pydantic model.
                                      ⚠️  Groq does NOT support OpenAI's proprietary
                                      client.beta.chat.completions.parse endpoint.
                                      Using it causes HTTP 400/404 errors on Groq's API.
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

import json
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

_MAX_HISTORY_MESSAGES = 8     # keep only last 8 messages to cap per-request token count
_RETRY_ATTEMPTS = 2           # number of retry attempts on transient failures
_RETRY_BASE_DELAY = 0.5       # initial backoff delay in seconds (doubles each attempt)

_FALLBACK_MESSAGE = (
    "I apologise — I'm experiencing a temporary connectivity issue with the AI service. "
    "Please resend your last message and we'll pick up right where we left off."
)

_FINAL_TURN_INJECTION = (
    "The interview is now complete. You have gathered sufficient signal across multiple "
    "curriculum days. Please now output the comprehensive, structured candidate evaluation "
    "as a raw JSON object — no markdown, no code fences, just the JSON. "
    "The object must have exactly these four keys:\n"
    "  - \"summary\": string — 3-5 sentence professional evaluation of the candidate's readiness.\n"
    "  - \"strengths\": array of strings — specific capabilities shown, citing curriculum day numbers.\n"
    "  - \"gaps\": array of strings — weaknesses or skipped modules, with curriculum day references.\n"
    "  - \"next\": array of strings — concrete, actionable next steps for the candidate.\n"
    "Be specific. Cite curriculum day numbers and names. Make each item actionable."
)


# ---------------------------------------------------------------------------
# LLMService
# ---------------------------------------------------------------------------


class LLMService:
    """
    Orchestrates all LLM API calls for the interview agent via Groq's API.

    Instantiated once at application startup as a module-level singleton.
    The underlying OpenAI-compatible client is thread-safe for concurrent requests.

    Client creation is lazy — the client object is only built on the first actual
    API call, so imports and tests succeed without a live API key configured.

    IMPORTANT — Groq Compatibility:
        Groq exposes an OpenAI-compatible REST API but does NOT implement the
        proprietary beta structured-output endpoint (client.beta.chat.completions.parse).
        Calling that endpoint against Groq results in HTTP 400 or 404 errors.

        For structured JSON output we instead:
          1. Pass response_format={"type": "json_object"} to the standard completions endpoint.
          2. Inject explicit schema instructions in a dedicated user message.
          3. Parse the raw JSON string manually with Feedback.model_validate_json().
    """

    def __init__(self) -> None:
        self.model: str = os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant")
        self._client: Optional[OpenAI] = None  # lazy init
        logger.info("LLMService initialised with model=%s (client lazy)", self.model)

    @property
    def client(self) -> OpenAI:
        """Return (and lazily create) the OpenAI-compatible client pointed at Groq."""
        if self._client is None:
            api_key = os.environ.get("GROQ_API_KEY", "").strip()
            base_url = os.environ.get("GROQ_BASE_URL", "https://api.groq.com/openai/v1").strip()

            if not api_key or api_key == "gsk_your-actual-groq-key-here":
                logger.warning(
                    "GROQ_API_KEY is not set or is a placeholder. "
                    "LLM calls will fail until a valid key is provided."
                )

            self._client = OpenAI(
                api_key=api_key or "placeholder",
                base_url=base_url,
                timeout=8.0,    # must complete before Vercel's 10s hobby-tier hard kill
                max_retries=0,  # we manage retries ourselves
            )
            logger.info(
                "Groq OpenAI-compatible client created: base_url=%s model=%s",
                base_url,
                self.model,
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

        Strips leading assistant messages after pruning to ensure the
        first message in the pruned window is always from 'user'.
        """
        if len(history) <= _MAX_HISTORY_MESSAGES:
            return history
        pruned = history[-_MAX_HISTORY_MESSAGES:]
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
        on transient Groq/OpenAI-SDK errors (rate limits, timeouts, connection drops).

        Raises the last exception if all retry attempts are exhausted.
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
                    "APIConnectionError on attempt %d/%d — retrying in %.1fs | cause: %s",
                    attempt, _RETRY_ATTEMPTS, delay, exc,
                    exc_info=True,
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
        """
        Standard chat completions call for normal interview conversation turns.
        Returns plain text response from the model.
        """
        response: ChatCompletion = self._call_with_retry(
            self.client.chat.completions.create,
            model=self.model,
            messages=messages,
            temperature=0.7,
            max_tokens=400,   # keep output short to stay well under Groq TPM limits
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
        Generate structured evaluation feedback compatible with the Groq API.

        ⚠️  GROQ COMPATIBILITY NOTE:
            Groq does NOT support client.beta.chat.completions.parse (OpenAI proprietary).
            Calling that endpoint against Groq returns HTTP 400/404.

        Implementation strategy:
          1. Inject a user message with explicit JSON schema instructions.
          2. Call the standard client.chat.completions.create with
             response_format={"type": "json_object"} — this is Groq-supported.
          3. Extract the raw JSON string from the response content.
          4. Strip any accidental markdown code fences (```json ... ```).
          5. Parse and validate using Feedback.model_validate_json().

        Returns:
            Tuple of (concluding_message: str, feedback: Feedback)
        """
        # Inject the structured JSON instruction as the final user message
        final_messages = messages + [
            {"role": "user", "content": _FINAL_TURN_INJECTION}
        ]

        # Standard completions call with json_object mode — fully Groq-compatible
        response: ChatCompletion = self._call_with_retry(
            self.client.chat.completions.create,
            model=self.model,
            messages=final_messages,
            response_format={"type": "json_object"},
            temperature=0.3,   # lower temperature for deterministic structured output
            max_tokens=2048,
        )

        raw_content: str = response.choices[0].message.content or "{}"

        # Strip markdown code fences if the model wraps its JSON output in them
        # e.g. ```json\n{...}\n```  →  {...}
        raw_content = raw_content.strip()
        if raw_content.startswith("```"):
            lines = raw_content.splitlines()
            # Drop first line (```json or ```) and last line (```)
            inner_lines = lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
            raw_content = "\n".join(inner_lines).strip()

        logger.debug("Raw structured feedback JSON: %.200s", raw_content)

        # Validate and parse into Feedback Pydantic model
        try:
            parsed_feedback = Feedback.model_validate_json(raw_content)
        except Exception as parse_exc:
            # Attempt lenient parse: some models return a top-level wrapper key
            logger.warning(
                "Direct JSON parse failed (%s) — attempting lenient extraction", parse_exc
            )
            try:
                raw_dict = json.loads(raw_content)
                # Unwrap if nested under a key like {"feedback": {...}}
                if len(raw_dict) == 1:
                    raw_dict = next(iter(raw_dict.values()))
                parsed_feedback = Feedback.model_validate(raw_dict)
            except Exception as fallback_exc:
                logger.error(
                    "Lenient JSON extraction also failed: %s", fallback_exc
                )
                raise fallback_exc

        logger.info(
            "Structured feedback compiled via json_object mode: "
            "strengths=%d, gaps=%d, next=%d, tokens_used=%d",
            len(parsed_feedback.strengths),
            len(parsed_feedback.gaps),
            len(parsed_feedback.next),
            response.usage.total_tokens if response.usage else -1,
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
            history:       Current conversation history (list of role/content dicts).
            is_final_turn: If True, invoke structured JSON feedback generation.

        Returns:
            A tuple of:
              - message (str): The agent's next message to send to the candidate.
              - feedback (Optional[Feedback]): Populated only when is_final_turn=True.

        Error handling:
            On any unrecoverable API failure after all retries, returns a graceful
            fallback message and (on final turn) a minimal fallback Feedback object,
            so the HTTP endpoint always returns 200 rather than 500.
        """
        # Build full message list: [system] + pruned_history
        pruned = self._prune_history(history)
        messages: List[Dict[str, str]] = [
            {"role": "system", "content": system_prompt},
            *pruned,
        ]

        try:
            if is_final_turn:
                logger.info(
                    "Invoking structured Feedback generation via json_object mode (final turn)"
                )
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
                    summary=(
                        "Unable to compile feedback due to a service interruption. "
                        "Please try again shortly."
                    ),
                    strengths=["Interview completed successfully"],
                    gaps=["Feedback compilation was interrupted by a service error"],
                    next=["Please restart the feedback generation by contacting support"],
                )
                return _FALLBACK_MESSAGE, fallback_feedback
            return _FALLBACK_MESSAGE, None


# ---------------------------------------------------------------------------
# Module-level singleton — import this in other modules
# ---------------------------------------------------------------------------

llm_service = LLMService()
