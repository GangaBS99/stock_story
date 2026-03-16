from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Always resolve .env relative to this file's package root so it works
# regardless of the directory uvicorn / streamlit is launched from.
_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Langfuse
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "http://localhost:3000"

    # LLM
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    # Control plane
    control_plane_url: str = "http://localhost:8500"

    # Dashboard alert thresholds
    alert_score_threshold: float = 0.6
    alert_error_rate_threshold: float = 0.2

    # Eval behaviour
    run_evals_async: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
