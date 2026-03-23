"""
Claw Researcher Configuration.

No MongoDB, no Redis, no MLflow. Just:
  - LLM provider config (API keys, models)
  - Research API config (Semantic Scholar, HuggingFace)
  - Workspace path (everything lives in files)
"""

from __future__ import annotations

from pathlib import Path
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Root configuration for Claw Researcher."""

    # Workspace — all files (memory, skills, reports, etc.) live here
    workspace: Path = Field(default=Path("."))

    # LLM
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    default_model: str = "anthropic/claude-sonnet-4-20250514"
    max_iterations: int = 40
    context_window_tokens: int = 128_000

    # Research APIs
    semantic_scholar_api_key: str = ""

    # Exec tool
    exec_enabled: bool = True
    exec_timeout: int = 60

    # General
    log_level: str = "INFO"
    debug: bool = False

    model_config = SettingsConfigDict(
        env_prefix="CLAW_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def ensure_workspace(self) -> Path:
        """Create workspace directories if they don't exist."""
        dirs = [
            self.workspace / "memory",
            self.workspace / "skills",
            self.workspace / "reports",
            self.workspace / "reproductions",
        ]
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)
        return self.workspace


@lru_cache()
def get_settings() -> Settings:
    """Get cached application settings (singleton)."""
    return Settings()
