"""Typed application configuration loaded from environment variables."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import Field, HttpUrl, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Validated settings with safe defaults for local fallback-only operation."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    azure_status_rss_url: HttpUrl = HttpUrl(
        "https://azure.status.microsoft/en-us/status/feed/"
    )
    rss_timeout_seconds: int = Field(default=10, gt=0)
    rss_max_retries: int = Field(default=1, ge=0)
    ingestion_interval_seconds: int = Field(default=300, gt=0)
    dashboard_poll_seconds: int = Field(default=30, gt=0)
    database_path: Path = Path("data/incidents.db")
    llm_provider: str = "none"
    llm_model: str = ""
    llm_api_key: SecretStr = SecretStr("")
    llm_timeout_seconds: int = Field(default=30, gt=0)
    llm_max_retries: int = Field(default=1, ge=0)
    log_level: str = "INFO"

    @field_validator("database_path", mode="before")
    @classmethod
    def validate_database_path(cls, value: Any) -> Any:
        """Reject blank, NUL-containing, and directory database paths."""
        if isinstance(value, str):
            if not value.strip():
                raise ValueError("DATABASE_PATH must not be blank")
            if "\x00" in value:
                raise ValueError("DATABASE_PATH must not contain NUL characters")
        path = Path(value)
        if path.exists() and path.is_dir():
            raise ValueError("DATABASE_PATH must point to a file, not a directory")
        return path

    @field_validator("log_level", mode="before")
    @classmethod
    def validate_log_level(cls, value: Any) -> str:
        """Normalize and validate standard Python logging levels."""
        level = str(value).strip().upper()
        allowed = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}
        if level not in allowed:
            raise ValueError(f"LOG_LEVEL must be one of {sorted(allowed)}")
        return level

    @property
    def fallback_only(self) -> bool:
        """Return whether analysis must use the deterministic local fallback."""
        return not bool(self.llm_api_key.get_secret_value())
