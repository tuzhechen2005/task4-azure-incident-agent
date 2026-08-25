"""Provider-neutral LLM client protocol and controlled error taxonomy."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol


class LLMErrorCategory(str, Enum):
    TIMEOUT = "TIMEOUT"
    PROVIDER = "PROVIDER"
    RATE_LIMIT = "RATE_LIMIT"
    AUTHENTICATION = "AUTHENTICATION"
    INVALID_RESPONSE = "INVALID_RESPONSE"


class LLMError(RuntimeError):
    """A safe provider-boundary failure with retry metadata."""

    category = LLMErrorCategory.PROVIDER
    retryable = False


class LLMTimeoutError(LLMError):
    category = LLMErrorCategory.TIMEOUT
    retryable = True


class LLMProviderError(LLMError):
    category = LLMErrorCategory.PROVIDER
    retryable = True


class LLMRateLimitError(LLMError):
    category = LLMErrorCategory.RATE_LIMIT
    retryable = True


class LLMAuthenticationError(LLMError):
    category = LLMErrorCategory.AUTHENTICATION
    retryable = False


class LLMInvalidResponseError(LLMError):
    category = LLMErrorCategory.INVALID_RESPONSE
    retryable = False


@dataclass(frozen=True, slots=True)
class LLMResponse:
    content: str
    model: str | None = None


class LLMClient(Protocol):
    """Small injectable client boundary; provider SDKs stay behind this interface."""

    def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        timeout_seconds: float,
    ) -> LLMResponse: ...
