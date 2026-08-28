from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.agents.azure_openai import AzureOpenAIClient
from app.agents.client import (
    LLMAuthenticationError,
    LLMInvalidResponseError,
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError,
)


class FakeResponses:
    def __init__(self, outcome: object) -> None:
        self.outcome = outcome
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


class FakeSDK:
    def __init__(self, outcome: object) -> None:
        self.responses = FakeResponses(outcome)


def client(outcome: object) -> tuple[AzureOpenAIClient, FakeSDK]:
    sdk = FakeSDK(outcome)
    return (
        AzureOpenAIClient(
            endpoint="https://example.openai.azure.com",
            api_key="test-secret",
            deployment="incident-agent",
            sdk_client=sdk,
        ),
        sdk,
    )


def test_generate_sends_prompts_schema_model_and_timeout() -> None:
    adapter, sdk = client(SimpleNamespace(output_text='{"incident_id":"inc-1"}'))

    response = adapter.generate(
        system_prompt="system",
        user_prompt="user",
        timeout_seconds=12,
    )

    assert response.content == '{"incident_id":"inc-1"}'
    assert response.model == "incident-agent"
    call = sdk.responses.calls[0]
    assert call["model"] == "incident-agent"
    assert call["timeout"] == 12
    assert call["input"] == [
        {"role": "system", "content": "system"},
        {"role": "user", "content": "user"},
    ]
    assert call["text"]["format"]["type"] == "json_schema"  # type: ignore[index]
    assert call["text"]["format"]["strict"] is True  # type: ignore[index]


def test_generate_rejects_empty_output() -> None:
    adapter, _ = client(SimpleNamespace(output_text=""))

    with pytest.raises(LLMInvalidResponseError):
        adapter.generate(system_prompt="s", user_prompt="u", timeout_seconds=5)


@pytest.mark.parametrize(
    ("error_name", "expected"),
    [
        ("APITimeoutError", LLMTimeoutError),
        ("RateLimitError", LLMRateLimitError),
        ("AuthenticationError", LLMAuthenticationError),
        ("APIConnectionError", LLMProviderError),
        ("APIError", LLMProviderError),
    ],
)
def test_generate_maps_provider_errors(
    error_name: str, expected: type[Exception]
) -> None:
    provider_error = type(error_name, (Exception,), {})("sensitive provider detail")
    adapter, _ = client(provider_error)

    with pytest.raises(expected) as caught:
        adapter.generate(system_prompt="s", user_prompt="u", timeout_seconds=5)

    assert "sensitive provider detail" not in str(caught.value)


def test_endpoint_is_normalized_to_azure_v1_base_url() -> None:
    created: dict[str, object] = {}

    def factory(**kwargs: object) -> FakeSDK:
        created.update(kwargs)
        return FakeSDK(SimpleNamespace(output_text="{}"))

    AzureOpenAIClient(
        endpoint="https://example.openai.azure.com/",
        api_key="test-secret",
        deployment="incident-agent",
        sdk_factory=factory,
    )

    assert created["base_url"] == "https://example.openai.azure.com/openai/v1/"
    assert created["api_key"] == "test-secret"
