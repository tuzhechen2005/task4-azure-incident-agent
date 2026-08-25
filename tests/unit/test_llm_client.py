from __future__ import annotations

from app.agents.client import (
    LLMAuthenticationError,
    LLMClient,
    LLMErrorCategory,
    LLMProviderError,
    LLMRateLimitError,
    LLMResponse,
    LLMTimeoutError,
)


class FakeLLMClient:
    def generate(
        self, *, system_prompt: str, user_prompt: str, timeout_seconds: float
    ) -> LLMResponse:
        del system_prompt, user_prompt, timeout_seconds
        return LLMResponse(content='{"ok":true}', model="fake-model")


def accepts_client(client: LLMClient) -> LLMResponse:
    return client.generate(
        system_prompt="system", user_prompt="user", timeout_seconds=1
    )


def test_fake_llm_client_contract() -> None:
    response = accepts_client(FakeLLMClient())

    assert response.content == '{"ok":true}'
    assert response.model == "fake-model"


def test_llm_error_categories() -> None:
    cases = [
        (LLMTimeoutError("timeout"), LLMErrorCategory.TIMEOUT, True),
        (LLMProviderError("provider"), LLMErrorCategory.PROVIDER, True),
        (LLMRateLimitError("rate"), LLMErrorCategory.RATE_LIMIT, True),
        (LLMAuthenticationError("auth"), LLMErrorCategory.AUTHENTICATION, False),
    ]

    for error, category, retryable in cases:
        assert error.category is category
        assert error.retryable is retryable
        assert str(error)
