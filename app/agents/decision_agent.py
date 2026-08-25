"""Validated Decision Agent with bounded repair and deterministic fallback."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from pydantic import ValidationError

from app.agents.client import LLMClient, LLMError
from app.agents.prompts import build_prompts
from app.models.schemas import (
    AgentInput,
    AnalysisSource,
    IncidentAnalysis,
    IncidentStatus,
    ResponsePlan,
    Severity,
)


class DecisionAgent:
    """Convert model responses into trusted analyses or safe local fallbacks."""

    def __init__(
        self,
        *,
        client: LLMClient | None,
        timeout_seconds: float,
        max_retries: int,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if max_retries < 0:
            raise ValueError("max_retries must not be negative")
        self._client = client
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def analyze(self, agent_input: AgentInput) -> IncidentAnalysis:
        """Return validated LLM output, falling back for every controlled failure."""
        if self._client is None:
            return self._fallback(agent_input, "missing credentials or client")

        prompts = build_prompts(agent_input)
        user_prompt = prompts.user
        last_reason = "invalid response"
        for attempt in range(self._max_retries + 1):
            try:
                response = self._client.generate(
                    system_prompt=prompts.system,
                    user_prompt=user_prompt,
                    timeout_seconds=self._timeout_seconds,
                )
                return self._validate_response(
                    content=response.content,
                    model=response.model,
                    agent_input=agent_input,
                )
            except LLMError as error:
                last_reason = error.category.value.lower().replace("_", " ")
                if not error.retryable:
                    break
            except (json.JSONDecodeError, ValidationError, ValueError, TypeError):
                last_reason = "invalid model response"
            except Exception:
                last_reason = "provider error"

            if attempt < self._max_retries:
                user_prompt = (
                    f"{prompts.user}\n\nThe previous response was invalid ({last_reason}). "
                    "Repair it and return one complete JSON object matching the contract."
                )

        return self._fallback(agent_input, last_reason)

    def _validate_response(
        self,
        *,
        content: str,
        model: str | None,
        agent_input: AgentInput,
    ) -> IncidentAnalysis:
        payload: Any = json.loads(content)
        if not isinstance(payload, dict):
            raise ValueError("model response must be one JSON object")
        payload["analyzed_at"] = self._now()
        payload["analysis_source"] = AnalysisSource.LLM
        payload["model"] = model
        analysis = IncidentAnalysis.model_validate(payload)
        if analysis.incident_id != agent_input.incident_id:
            raise ValueError("analysis incident_id does not match input")
        return analysis

    def _fallback(self, agent_input: AgentInput, reason: str) -> IncidentAnalysis:
        active_or_monitoring = agent_input.status in {
            IncidentStatus.ACTIVE,
            IncidentStatus.MONITORING,
        }
        severity = Severity.SEV_3 if active_or_monitoring else Severity.SEV_4
        confidence = 0.25 if active_or_monitoring else 0.35
        impact = (
            [
                "Matching workloads may experience disruption; verify against local telemetry."
            ]
            if active_or_monitoring
            else [
                "No active workload impact is confirmed by the supplied public notice."
            ]
        )
        return IncidentAnalysis(
            incident_id=agent_input.incident_id,
            severity=severity,
            confidence=confidence,
            affected_services=agent_input.services,
            affected_regions=agent_input.regions,
            scope="Public status information only; tenant-specific scope is not confirmed.",
            summary=agent_input.title,
            potential_impact=impact,
            recommended_actions=[
                "Verify actual impact using application and platform telemetry.",
                "Monitor the linked public status source for updates.",
                "Escalate through established support channels if local impact is confirmed.",
            ],
            response_plan=ResponsePlan(
                immediate_actions=[
                    "Confirm whether affected services and regions match deployed workloads."
                ],
                investigation_steps=[
                    "Review error rates, latency, availability, and recent deployment changes."
                ],
                mitigation_options=[
                    "Use only pre-approved retries, failover, or workload workarounds."
                ],
                communication_plan=[
                    "Share verified local impact and cite the public source without overstating scope."
                ],
                recovery_checks=[
                    "Confirm local metrics return to baseline before declaring recovery."
                ],
                escalation_conditions=[
                    "Escalate if impact expands, critical workloads stop, or data integrity is at risk."
                ],
            ),
            rationale=(
                "Conservative fallback severity based on normalized status because no valid "
                "model assessment was available."
            ),
            analyzed_at=self._now(),
            analysis_source=AnalysisSource.FALLBACK,
            model=None,
            warnings=[
                f"Deterministic fallback used: {reason}.",
                "Public status data does not confirm tenant-specific impact.",
            ],
        )

    def _now(self) -> datetime:
        now = self._clock()
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("clock must return a timezone-aware datetime")
        return now.astimezone(timezone.utc)
