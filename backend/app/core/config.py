"""Application configuration. Every secret comes from the environment."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "Palm Hills Resident Assistant API"
    environment: str = "development"
    debug: bool = False

    # --- Database -------------------------------------------------------
    database_url: str = "postgresql+psycopg://palmhills:palmhills@localhost:5432/palmhills"

    # --- Dataset --------------------------------------------------------
    dataset_path: str = str(REPO_ROOT / "data" / "palm_hills_regulations_v1.0.json")

    # --- Embeddings -----------------------------------------------------
    # hash   : deterministic, offline, no model download. Dev/test default.
    # local  : sentence-transformers multilingual model (real semantic search).
    # voyage : Voyage AI hosted embeddings (requires VOYAGE_API_KEY).
    embedding_provider: str = "hash"
    embedding_model: str = "intfloat/multilingual-e5-base"
    embedding_dim: int = 768
    voyage_api_key: str | None = None

    # --- LLM ------------------------------------------------------------
    # claude   : Anthropic Messages API.
    # template : deterministic, no network. Used by tests and as the fallback
    #            whenever the configured provider is unavailable.
    llm_provider: str = "template"
    anthropic_api_key: str | None = None
    llm_model: str = "claude-opus-5"
    llm_effort: str = "low"
    llm_max_tokens: int = 4000
    llm_timeout_seconds: float = 30.0

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
