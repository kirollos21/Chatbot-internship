"""Application configuration. Every secret comes from the environment."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]

# Per-provider model defaults. Keeping these keyed by provider means switching
# LLM_PROVIDER without also editing LLM_MODEL cannot send one vendor's model ID
# to another vendor's endpoint.
DEFAULT_LLM_MODEL: dict[str, str] = {
    "gemini": "gemini-2.5-flash",
    "claude": "claude-opus-5",
}
DEFAULT_EMBEDDING_MODEL: dict[str, str] = {
    "gemini": "gemini-embedding-2",
    "local": "intfloat/multilingual-e5-base",
    "voyage": "voyage-3",
}


class Settings(BaseSettings):
    # Absolute paths: a relative ".env" resolves against the *current working
    # directory*, so running from backend/ (as the launcher and the ingest
    # script do) would silently miss the repo-root .env and fall back to
    # defaults. Later entries win, so a backend/.env can override the root one.
    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", REPO_ROOT / "backend" / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Palm Hills Resident Assistant API"
    environment: str = "development"
    debug: bool = False

    # --- Database -------------------------------------------------------
    database_url: str = "postgresql+psycopg://palmhills:palmhills@localhost:5432/palmhills"

    # pgvector is the production target, but it ships no Windows binaries, so a
    # stock local PostgreSQL cannot load it without MSVC or a container.
    # Setting this false drops the vector column and index and ranks on trigram
    # similarity alone (pg_trgm is bundled with PostgreSQL). Retrieval quality
    # is lower — it becomes lexical-only — so keep it true wherever pgvector is
    # available. `/health/ready` reports which mode is live.
    vector_enabled: bool = True

    # --- Dataset --------------------------------------------------------
    dataset_path: str = str(REPO_ROOT / "data" / "palm_hills_regulations_v1.0.json")

    # --- Embeddings -----------------------------------------------------
    # hash   : deterministic, offline, no model download. Dev/test default.
    # gemini : Gemini embeddings (reuses GEMINI_API_KEY).
    # local  : sentence-transformers multilingual model.
    # voyage : Voyage AI hosted embeddings (requires VOYAGE_API_KEY).
    embedding_provider: str = "hash"
    # Leave unset to take the provider's own default (see DEFAULT_EMBEDDING_MODEL);
    # a single shared default would send one provider's model ID to another.
    embedding_model: str | None = None
    embedding_dim: int = 768
    voyage_api_key: str | None = None

    # --- LLM ------------------------------------------------------------
    # gemini   : Google Gemini (generateContent).
    # claude   : Anthropic Messages API (kept so the layer stays provider-neutral).
    # template : deterministic, no network. Used by tests and as the fallback
    #            whenever the configured provider is unavailable.
    llm_provider: str = "gemini"
    gemini_api_key: str | None = None
    anthropic_api_key: str | None = None
    # Leave unset to take the provider's own default (see DEFAULT_LLM_MODEL).
    llm_model: str | None = None
    llm_max_tokens: int = 4000
    llm_timeout_seconds: float = 30.0

    # Gemini-specific. gemini-2.5-flash is a thinking model with thinking ON by
    # default; a budget of 0 disables it. This task is a grounded rewrite of
    # records the retriever already selected, so thinking buys little and risks
    # the known 2.5 failure mode where reasoning consumes max_output_tokens and
    # the response comes back empty with finish_reason=MAX_TOKENS.
    llm_thinking_budget: int = 0
    llm_temperature: float = 0.2

    # Claude-specific (ignored by other providers).
    llm_effort: str = "low"

    # --- Retrieval / confidence ----------------------------------------
    retrieval_top_k: int = 8
    confidence_high: float = 0.62
    confidence_low: float = 0.34
    vector_weight: float = 0.55
    lexical_weight: float = 0.45

    # --- Security -------------------------------------------------------
    # Comma-separated list. Empty => auth disabled (local development only).
    api_keys: str = ""
    rate_limit_per_minute: int = 60
    max_upload_bytes: int = 5 * 1024 * 1024
    allowed_upload_types: str = "image/jpeg,image/png,image/webp"
    cors_origins: str = "*"

    @property
    def dataset_file(self) -> Path:
        """Dataset path resolved against the repo root, not the CWD."""
        path = Path(self.dataset_path)
        return path if path.is_absolute() else (REPO_ROOT / path).resolve()

    @property
    def resolved_llm_model(self) -> str:
        return self.llm_model or DEFAULT_LLM_MODEL.get(self.llm_provider.lower(), "")

    @property
    def resolved_embedding_model(self) -> str:
        return self.embedding_model or DEFAULT_EMBEDDING_MODEL.get(
            self.embedding_provider.lower(), ""
        )

    @property
    def api_key_set(self) -> set[str]:
        return {k.strip() for k in self.api_keys.split(",") if k.strip()}

    @property
    def allowed_upload_type_set(self) -> set[str]:
        return {t.strip() for t in self.allowed_upload_types.split(",") if t.strip()}

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
