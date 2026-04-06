"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os
from pathlib import Path
from functools import lru_cache

from pydantic_settings import BaseSettings
from pydantic import Field, model_validator


class Settings(BaseSettings):
    """Central configuration — single source of truth for all env vars."""

    # --- Provider Selection ---
    model_provider: str = Field(default="gemini", description="gemini|openai|anthropic|ollama")
    embedding_provider: str = Field(default="gemini", description="gemini|openai|ollama")

    # --- Gemini ---
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"

    # --- OpenAI ---
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"

    # --- Anthropic ---
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-20250514"

    # --- Ollama ---
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3:4b"
    ollama_embed_model: str = "nomic-embed-text"

    # --- Feature Flags ---
    enable_graph_memory: bool = False
    enable_provider_failover: bool = False
    enable_langsmith: bool = False

    # --- LangSmith ---
    langchain_tracing_v2: bool = False
    langchain_api_key: str = ""
    langchain_project: str = "sop-agent"

    # --- Paths ---
    database_path: str = "./data/sop_agent.db"
    chromadb_path: str = "./data/chromadb"
    upload_path: str = "./data/uploads"

    # --- Application ---
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:8501,http://localhost:3000"

    # --- Rate Limiting ---
    rate_limit_rpm: int = 60
    rate_limit_tpm: int = 100000

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    @model_validator(mode="after")
    def validate_credentials(self) -> "Settings":
        """Validate that required API keys are present for the selected provider."""
        provider = self.model_provider.lower()
        if provider == "gemini" and not self.gemini_api_key:
            _warn_missing_key("GEMINI_API_KEY", provider)
        elif provider == "openai" and not self.openai_api_key:
            _warn_missing_key("OPENAI_API_KEY", provider)
        elif provider == "anthropic" and not self.anthropic_api_key:
            _warn_missing_key("ANTHROPIC_API_KEY", provider)

        embed_provider = self.embedding_provider.lower()
        if embed_provider == "gemini" and not self.gemini_api_key:
            _warn_missing_key("GEMINI_API_KEY", f"embedding/{embed_provider}")
        elif embed_provider == "openai" and not self.openai_api_key:
            _warn_missing_key("OPENAI_API_KEY", f"embedding/{embed_provider}")
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def ensure_directories(self) -> None:
        """Create data directories if they don't exist."""
        for p in (self.database_path, self.chromadb_path, self.upload_path):
            path = Path(p)
            directory = path.parent if path.suffix else path
            directory.mkdir(parents=True, exist_ok=True)


def _warn_missing_key(key: str, provider: str) -> None:
    import logging
    logging.getLogger("sop_agent.config").warning(
        "API key %s not set for provider %s — LLM calls will fail", key, provider
    )


@lru_cache
def get_settings() -> Settings:
    """Return cached settings singleton."""
    settings = Settings()
    settings.ensure_directories()
    return settings
