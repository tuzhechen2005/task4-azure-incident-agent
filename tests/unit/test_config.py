from __future__ import annotations

import io
import logging
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.config import Settings
from app.logging_config import configure_logging


def load_settings() -> Settings:
    """Load environment settings without consulting a developer's local .env file."""
    return Settings(_env_file=None)  # type: ignore[call-arg]


def test_settings_defaults() -> None:
    settings = load_settings()

    assert str(settings.azure_status_rss_url).startswith("https://")
    assert settings.rss_timeout_seconds == 10
    assert settings.rss_max_retries == 1
    assert settings.ingestion_interval_seconds == 300
    assert settings.dashboard_poll_seconds == 30
    assert settings.database_path == Path("data/incidents.db")
    assert settings.llm_provider == "none"
    assert settings.llm_model == ""
    assert settings.llm_timeout_seconds == 30
    assert settings.llm_max_retries == 1
    assert settings.azure_openai_endpoint is None
    assert settings.azure_openai_deployment == ""
    assert settings.azure_openai_api_key.get_secret_value() == ""
    assert settings.log_level == "INFO"


def test_settings_environment_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AZURE_STATUS_RSS_URL", "https://example.test/azure.xml")
    monkeypatch.setenv("RSS_TIMEOUT_SECONDS", "7")
    monkeypatch.setenv("RSS_MAX_RETRIES", "2")
    monkeypatch.setenv("INGESTION_INTERVAL_SECONDS", "60")
    monkeypatch.setenv("DASHBOARD_POLL_SECONDS", "15")
    monkeypatch.setenv("DATABASE_PATH", "var/test.db")
    monkeypatch.setenv("LLM_PROVIDER", "example")
    monkeypatch.setenv("LLM_MODEL", "model-1")
    monkeypatch.setenv("LLM_API_KEY", "top-secret")
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "9")
    monkeypatch.setenv("LLM_MAX_RETRIES", "3")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "incident-agent")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "azure-secret")
    monkeypatch.setenv("LOG_LEVEL", "debug")

    settings = load_settings()

    assert str(settings.azure_status_rss_url) == "https://example.test/azure.xml"
    assert settings.rss_timeout_seconds == 7
    assert settings.rss_max_retries == 2
    assert settings.ingestion_interval_seconds == 60
    assert settings.dashboard_poll_seconds == 15
    assert settings.database_path == Path("var/test.db")
    assert settings.llm_provider == "example"
    assert settings.llm_model == "model-1"
    assert settings.llm_api_key.get_secret_value() == "top-secret"
    assert settings.llm_timeout_seconds == 9
    assert settings.llm_max_retries == 3
    assert str(settings.azure_openai_endpoint) == "https://example.openai.azure.com/"
    assert settings.azure_openai_deployment == "incident-agent"
    assert settings.azure_openai_api_key.get_secret_value() == "azure-secret"
    assert settings.log_level == "DEBUG"


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("RSS_TIMEOUT_SECONDS", "0"),
        ("INGESTION_INTERVAL_SECONDS", "-1"),
        ("DASHBOARD_POLL_SECONDS", "0"),
        ("LLM_TIMEOUT_SECONDS", "-2"),
        ("RSS_MAX_RETRIES", "-1"),
        ("LLM_MAX_RETRIES", "-1"),
        ("DATABASE_PATH", ""),
    ],
)
def test_settings_reject_invalid_intervals(
    monkeypatch: pytest.MonkeyPatch, name: str, value: str
) -> None:
    monkeypatch.setenv(name, value)

    with pytest.raises(ValidationError) as error:
        load_settings()

    assert name.lower() in str(error.value).lower()


def test_settings_missing_llm_key_enables_fallback_mode() -> None:
    settings = load_settings()

    assert settings.llm_api_key.get_secret_value() == ""
    assert settings.fallback_only is True


def test_complete_azure_openai_settings_enable_real_agent() -> None:
    settings = Settings.model_validate(
        {
            "llm_provider": "azure_openai",
            "azure_openai_endpoint": "https://example.openai.azure.com",
            "azure_openai_deployment": "incident-agent",
            "azure_openai_api_key": "test-key",
        }
    )

    assert settings.fallback_only is False


@pytest.mark.parametrize(
    "missing_field",
    ["azure_openai_endpoint", "azure_openai_deployment", "azure_openai_api_key"],
)
def test_incomplete_azure_openai_settings_use_fallback(missing_field: str) -> None:
    values = {
        "llm_provider": "azure_openai",
        "azure_openai_endpoint": "https://example.openai.azure.com",
        "azure_openai_deployment": "incident-agent",
        "azure_openai_api_key": "test-key",
    }
    values[missing_field] = ""

    assert Settings.model_validate(values).fallback_only is True


def test_logging_redacts_secret_values() -> None:
    output = io.StringIO()
    secret = "credential-that-must-not-leak"
    configure_logging(level="INFO", secrets=[secret], stream=output)

    logging.getLogger("test").info("provider key=%s", secret)

    rendered = output.getvalue()
    assert secret not in rendered
    assert "[REDACTED]" in rendered
