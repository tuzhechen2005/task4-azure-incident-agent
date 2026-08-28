"""Azure OpenAI Responses API adapter for the provider-neutral LLM boundary."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, cast

from app.agents.client import (
    LLMAuthenticationError,
    LLMInvalidResponseError,
    LLMProviderError,
    LLMRateLimitError,
    LLMResponse,
    LLMTimeoutError,
)


class ResponsesResource(Protocol):
    def create(self, **kwargs: object) -> object: ...


class OpenAISDKClient(Protocol):
    @property
    def responses(self) -> ResponsesResource: ...


SDKFactory = Callable[..., OpenAISDKClient]


def _response_schema() -> dict[str, object]:
    string_array: dict[str, object] = {"type": "array", "items": {"type": "string"}}
    plan_properties = {
        name: string_array
        for name in (
            "immediate_actions",
            "investigation_steps",
            "mitigation_options",
            "communication_plan",
            "recovery_checks",
            "escalation_conditions",
        )
    }
    properties: dict[str, object] = {
        "incident_id": {"type": "string"},
        "severity": {"type": "string", "enum": ["SEV-1", "SEV-2", "SEV-3", "SEV-4"]},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "affected_services": string_array,
        "affected_regions": string_array,
        "scope": {"type": "string"},
        "summary": {"type": "string"},
        "potential_impact": string_array,
        "recommended_actions": string_array,
        "response_plan": {
            "type": "object",
            "properties": plan_properties,
            "required": list(plan_properties),
            "additionalProperties": False,
        },
        "rationale": {"type": "string"},
        "analyzed_at": {"type": "string"},
        "analysis_source": {"type": "string", "enum": ["LLM"]},
        "model": {"type": ["string", "null"]},
        "warnings": string_array,
    }
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


class AzureOpenAIClient:
    """Call one Azure OpenAI deployment and return validated JSON text upstream."""

    def __init__(
        self,
        *,
        endpoint: str,
        api_key: str,
        deployment: str,
        sdk_client: OpenAISDKClient | None = None,
        sdk_factory: SDKFactory | None = None,
    ) -> None:
        if not endpoint.strip() or not api_key or not deployment.strip():
            raise ValueError("Azure OpenAI endpoint, key, and deployment are required")
        self._deployment = deployment.strip()
        if sdk_client is not None:
            self._client = sdk_client
            return
        if sdk_factory is None:
            from openai import OpenAI

            sdk_factory = cast(SDKFactory, OpenAI)
        base_url = f"{endpoint.rstrip('/')}/openai/v1/"
        self._client = sdk_factory(base_url=base_url, api_key=api_key)

    def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        timeout_seconds: float,
    ) -> LLMResponse:
        try:
            response = self._client.responses.create(
                model=self._deployment,
                input=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "azure_incident_analysis",
                        "description": "Validated Azure public incident assessment",
                        "strict": True,
                        "schema": _response_schema(),
                    }
                },
                timeout=timeout_seconds,
            )
        except Exception as error:
            self._raise_mapped_error(error)
        content = getattr(response, "output_text", None)
        if not isinstance(content, str) or not content.strip():
            raise LLMInvalidResponseError("Azure OpenAI returned no text output")
        return LLMResponse(content=content, model=self._deployment)

    @staticmethod
    def _raise_mapped_error(error: Exception) -> None:
        error_name = type(error).__name__
        safe_message = "Azure OpenAI request failed"
        if error_name == "APITimeoutError":
            raise LLMTimeoutError(safe_message) from error
        if error_name == "RateLimitError":
            raise LLMRateLimitError(safe_message) from error
        if error_name == "AuthenticationError":
            raise LLMAuthenticationError(safe_message) from error
        if error_name in {"APIConnectionError", "APIError", "InternalServerError"}:
            raise LLMProviderError(safe_message) from error
        raise LLMProviderError(safe_message) from error
