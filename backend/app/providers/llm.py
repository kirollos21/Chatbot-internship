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
    if provider == "claude":
        if not settings.anthropic_api_key:
            logger.warning("LLM_PROVIDER=claude but ANTHROPIC_API_KEY is unset; using template provider.")
            return TemplateProvider()
        try:
            return ClaudeProvider(
                api_key=settings.anthropic_api_key,
                model=settings.llm_model,
                max_tokens=settings.llm_max_tokens,
                effort=settings.llm_effort,
                timeout=settings.llm_timeout_seconds,
            )
        except ImportError:  # pragma: no cover
            logger.warning("anthropic SDK not installed; using template provider.")
            return TemplateProvider()
    return TemplateProvider()
