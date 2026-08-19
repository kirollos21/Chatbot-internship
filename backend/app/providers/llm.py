"""LLM provider abstraction.

The assistant must work with or without a hosted model, so the interface allows
a provider to decline to answer (`text is None`). The answer service then falls
back to a deterministic, template-rendered answer built directly from the
retrieved records — the resident still gets the verified rule and the exact
penalty, only phrased less naturally.

The LLM is never the authority on Palm Hills policy. It receives the retrieved
records and rewrites them; `app.services.answer` re-checks every figure it
produces before the answer leaves the process.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import lru_cache

from app.core.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class LLMResult:
    text: str | None
    provider: str
    model: str | None = None
    refused: bool = False
    error: str | None = None


class LLMProvider(ABC):
    name: str = "base"

    @abstractmethod
    def generate(self, system_prompt: str, user_prompt: str) -> LLMResult:
        ...


class TemplateProvider(LLMProvider):
    """No-network provider. Declines, so the deterministic renderer is used."""

    name = "template"

    def generate(self, system_prompt: str, user_prompt: str) -> LLMResult:
        return LLMResult(text=None, provider=self.name)


class GeminiProvider(LLMProvider):
    """Google Gemini via the generateContent API.

    Uses `client.models.generate_content` rather than the newer Interactions
    API: Google documents generateContent as the recommended path for stable
    production deployments, and this call is single-turn with no tools or
    server-side conversation state, so Interactions would add a dependency on a
    newer surface for no gain here.
    """

    name = "gemini"

    def __init__(
        self,
        api_key: str,
        model: str,
        max_tokens: int,
        temperature: float,
        thinking_budget: int,
        timeout: float,
    ) -> None:
        from google import genai
        from google.genai import errors, types

        self._errors = errors
        self._types = types
        # The SDK takes the timeout in milliseconds via http_options.
        self._client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=int(timeout * 1000)),
        )
        self._model = model
        self._config = types.GenerateContentConfig(
            system_instruction=None,  # set per request below
            max_output_tokens=max_tokens,
            temperature=temperature,
            thinking_config=types.ThinkingConfig(thinking_budget=thinking_budget),
            # We pass no tools, so automatic function calling is irrelevant;
            # disabling it silences a warning the SDK logs on every call.
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )

    def generate(self, system_prompt: str, user_prompt: str) -> LLMResult:
        types = self._types
        config = self._config.model_copy(update={"system_instruction": system_prompt})

        try:
            response = self._client.models.generate_content(
                model=self._model,
                contents=user_prompt,
                config=config,
            )
        except self._errors.APIError as exc:
            logger.warning("Gemini API error %s: %s", exc.code, exc.message)
            return LLMResult(None, self.name, self._model, error=f"api_status_{exc.code}")
        except Exception as exc:  # transport/DNS/timeout - fall back, never 500
            logger.warning("Gemini call failed: %s", type(exc).__name__)
            return LLMResult(None, self.name, self._model, error="connection")

        # A safety filter can block the prompt outright, or stop generation
        # mid-candidate. Either way there is no answer to trust, so decline and
        # let the deterministic renderer take over.
        feedback = getattr(response, "prompt_feedback", None)
        if feedback is not None and getattr(feedback, "block_reason", None):
            return LLMResult(None, self.name, self._model, refused=True, error="prompt_blocked")

        candidates = getattr(response, "candidates", None) or []
        finish_reason = str(getattr(candidates[0], "finish_reason", "")) if candidates else ""
        if "SAFETY" in finish_reason or "RECITATION" in finish_reason or "BLOCK" in finish_reason:
            return LLMResult(None, self.name, self._model, refused=True, error="response_blocked")

        # `response.text` raises rather than returning None on some blocked
        # responses, so it is guarded too.
        try:
            text = (response.text or "").strip()
        except Exception:
            text = ""

        if not text:
            # Most often finish_reason=MAX_TOKENS with the budget spent on
            # thinking. Declining keeps a truncated half-answer off the screen.
            reason = "truncated_or_empty" if "MAX_TOKENS" in finish_reason else "empty_response"
            return LLMResult(None, self.name, self._model, error=reason)

        return LLMResult(text, self.name, self._model)


class ClaudeProvider(LLMProvider):
    name = "claude"

    def __init__(self, api_key: str, model: str, max_tokens: int, effort: str, timeout: float) -> None:
        import anthropic

        self._anthropic = anthropic
        self._client = anthropic.Anthropic(api_key=api_key, timeout=timeout)
        self._model = model
        self._max_tokens = max_tokens
        self._effort = effort

    def generate(self, system_prompt: str, user_prompt: str) -> LLMResult:
        anthropic = self._anthropic
        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                system=[{"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}],
                output_config={"effort": self._effort},
                messages=[{"role": "user", "content": user_prompt}],
            )
        except anthropic.APIStatusError as exc:
            logger.warning("Claude API error %s: %s", exc.status_code, exc.message)
            return LLMResult(None, self.name, self._model, error=f"api_status_{exc.status_code}")
        except anthropic.APIConnectionError as exc:
            logger.warning("Claude connection error: %s", exc)
            return LLMResult(None, self.name, self._model, error="connection")

        # Safety classifiers can decline; `content` is then empty or partial.
        if response.stop_reason == "refusal":
            return LLMResult(None, self.name, self._model, refused=True, error="refusal")

        text = "".join(block.text for block in response.content if block.type == "text").strip()
        if not text:
            return LLMResult(None, self.name, self._model, error="empty_response")
        return LLMResult(text, self.name, self._model)


@lru_cache
def get_llm_provider() -> LLMProvider:
    settings = get_settings()
    provider = settings.llm_provider.lower()

    if provider == "gemini":
        if not settings.gemini_api_key:
            logger.warning("LLM_PROVIDER=gemini but GEMINI_API_KEY is unset; using template provider.")
            return TemplateProvider()
        try:
            return GeminiProvider(
                api_key=settings.gemini_api_key,
                model=settings.resolved_llm_model,
                max_tokens=settings.llm_max_tokens,
                temperature=settings.llm_temperature,
                thinking_budget=settings.llm_thinking_budget,
                timeout=settings.llm_timeout_seconds,
            )
        except ImportError:  # pragma: no cover
            logger.warning("google-genai not installed; using template provider.")
            return TemplateProvider()

    if provider == "claude":
        if not settings.anthropic_api_key:
            logger.warning("LLM_PROVIDER=claude but ANTHROPIC_API_KEY is unset; using template provider.")
            return TemplateProvider()
        try:
            return ClaudeProvider(
                api_key=settings.anthropic_api_key,
                model=settings.resolved_llm_model,
                max_tokens=settings.llm_max_tokens,
                effort=settings.llm_effort,
                timeout=settings.llm_timeout_seconds,
            )
        except ImportError:  # pragma: no cover
            logger.warning("anthropic SDK not installed; using template provider.")
            return TemplateProvider()
    return TemplateProvider()
