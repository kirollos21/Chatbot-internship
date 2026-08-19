"""Provider selection and safe degradation.

No network. These lock in the two properties that keep a provider swap from
breaking the assistant: the right model ID goes to the right vendor, and a
provider that cannot answer declines rather than raising.
"""

from __future__ import annotations

import pytest

from app.core.config import DEFAULT_EMBEDDING_MODEL, DEFAULT_LLM_MODEL, Settings
from app.providers.llm import LLMResult, TemplateProvider


# --- per-provider model defaults ---------------------------------------

def test_gemini_is_the_default_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    # The test session pins LLM_PROVIDER=template; clear it to see the code default.
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    settings = Settings(_env_file=None)
    assert settings.llm_provider == "gemini"
    assert settings.resolved_llm_model == "gemini-2.5-flash"


def test_environment_overrides_the_code_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "claude")
    assert Settings(_env_file=None).llm_provider == "claude"


def test_switching_provider_switches_the_model_default() -> None:
    """The bug this prevents: sending a Gemini model ID to Anthropic."""
    gemini = Settings(_env_file=None, llm_provider="gemini")
    claude = Settings(_env_file=None, llm_provider="claude")
    assert gemini.resolved_llm_model == "gemini-2.5-flash"
    assert claude.resolved_llm_model == "claude-opus-5"
    assert gemini.resolved_llm_model != claude.resolved_llm_model


def test_explicit_model_overrides_the_default() -> None:
    settings = Settings(_env_file=None, llm_provider="gemini", llm_model="gemini-2.5-pro")
    assert settings.resolved_llm_model == "gemini-2.5-pro"


def test_blank_model_falls_back_to_the_default() -> None:
    """docker-compose passes LLM_MODEL="" when the var is unset."""
    settings = Settings(_env_file=None, llm_provider="gemini", llm_model="")
    assert settings.resolved_llm_model == "gemini-2.5-flash"


@pytest.mark.parametrize("provider", sorted(DEFAULT_EMBEDDING_MODEL))
def test_every_embedding_provider_has_a_model_default(provider: str) -> None:
    settings = Settings(_env_file=None, embedding_provider=provider)
    assert settings.resolved_embedding_model


@pytest.mark.parametrize("provider", sorted(DEFAULT_LLM_MODEL))
def test_every_llm_provider_has_a_model_default(provider: str) -> None:
    settings = Settings(_env_file=None, llm_provider=provider)
    assert settings.resolved_llm_model


# --- degradation --------------------------------------------------------

def test_template_provider_declines_so_the_renderer_takes_over() -> None:
    result = TemplateProvider().generate("system", "user")
    assert result.text is None
    assert result.provider == "template"


def test_missing_gemini_key_degrades_to_template(monkeypatch: pytest.MonkeyPatch) -> None:
    """No key must not crash the API - answers fall back to templates."""
    import app.providers.llm as llm

    monkeypatch.setattr(
        llm, "get_settings", lambda: Settings(_env_file=None, llm_provider="gemini", gemini_api_key=None)
    )
    llm.get_llm_provider.cache_clear()
    try:
        assert isinstance(llm.get_llm_provider(), TemplateProvider)
    finally:
        llm.get_llm_provider.cache_clear()


def test_missing_gemini_key_rejects_gemini_embeddings() -> None:
    """Embeddings fail loudly instead: a silent fallback would corrupt the index."""
    import app.providers.embeddings as emb

    settings = Settings(_env_file=None, embedding_provider="gemini", gemini_api_key=None)
    original = emb.get_settings
    emb.get_settings = lambda: settings  # type: ignore[assignment]
    emb.get_embedding_provider.cache_clear()
    try:
        with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
            emb.get_embedding_provider()
    finally:
        emb.get_settings = original  # type: ignore[assignment]
        emb.get_embedding_provider.cache_clear()


def test_llm_result_carries_refusal_state() -> None:
    result = LLMResult(None, "gemini", "gemini-2.5-flash", refused=True, error="prompt_blocked")
    assert result.text is None and result.refused
