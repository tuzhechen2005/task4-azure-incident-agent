from __future__ import annotations

import json
from datetime import datetime, timezone

from app.agents.client import LLMClient, LLMProviderError, LLMResponse, LLMTimeoutError
from app.agents.decision_agent import DecisionAgent
from app.models.schemas import AgentInput, AnalysisSource, IncidentStatus, Severity

NOW = datetime(2026, 8, 25, 7, 0, tzinfo=timezone.utc)


class QueueClient:
    def __init__(self, outcomes: list[LLMResponse | Exception]) -> None:
        self.outcomes = outcomes
        self.calls: list[tuple[str, str, float]] = []

    def generate(
        self, *, system_prompt: str, user_prompt: str, timeout_seconds: float
    ) -> LLMResponse:
        self.calls.append((system_prompt, user_prompt, timeout_seconds))
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def input_for(status: IncidentStatus = IncidentStatus.ACTIVE) -> AgentInput:
    return AgentInput.model_validate(
        {
            "incident_id": "inc-1",
            "title": "Azure SQL degradation",
            "description": "Intermittent database connection errors are reported.",
            "services": ["Azure SQL"],
            "regions": ["East US"],
            "status": status,
            "published_at": NOW,
            "source_link": "https://example.test/incidents/1",
        }
    )


def valid_payload(severity: str = "SEV-3", **overrides: object) -> str:
    payload: dict[str, object] = {
        "incident_id": "inc-1",
        "severity": severity,
        "confidence": 0.8,
        "affected_services": ["Azure SQL"],
        "affected_regions": ["East US"],
        "scope": "Some database workloads may see intermittent errors.",
        "summary": "Azure SQL connectivity is degraded in East US.",
        "potential_impact": ["Database requests may fail"],
        "recommended_actions": ["Review workload telemetry"],
        "response_plan": {
            "immediate_actions": ["Confirm actual workload impact"],
            "investigation_steps": ["Review error rates"],
            "mitigation_options": ["Use a tested retry policy"],
            "communication_plan": ["Update service owners"],
            "recovery_checks": ["Confirm errors return to baseline"],
            "escalation_conditions": ["Escalate if impact expands"],
        },
        "rationale": "The source reports limited regional degradation.",
        "analyzed_at": "2020-01-01T00:00:00Z",
        "analysis_source": "LLM",
        "model": None,
        "warnings": [],
    }
    payload.update(overrides)
    return json.dumps(payload)


def agent(
    client: LLMClient | None, *, retries: int = 0, timeout: float = 5
) -> DecisionAgent:
    return DecisionAgent(
        client=client,
        timeout_seconds=timeout,
        max_retries=retries,
        clock=lambda: NOW,
    )


def test_valid_llm_analysis() -> None:
    client = QueueClient([LLMResponse(valid_payload(), model="fake-v1")])

    result = agent(client).analyze(input_for())

    assert result.analysis_source is AnalysisSource.LLM
    assert result.model == "fake-v1"
    assert result.analyzed_at == NOW
    assert result.incident_id == "inc-1"


def assert_accepts_severity(severity: Severity) -> None:
    client = QueueClient([LLMResponse(valid_payload(severity.value), model="fake")])

    assert agent(client).analyze(input_for()).severity is severity


def test_accepts_sev1() -> None:
    assert_accepts_severity(Severity.SEV_1)


def test_accepts_sev2() -> None:
    assert_accepts_severity(Severity.SEV_2)


def test_accepts_sev3() -> None:
    assert_accepts_severity(Severity.SEV_3)


def test_accepts_sev4() -> None:
    assert_accepts_severity(Severity.SEV_4)


def test_invalid_json_uses_fallback() -> None:
    result = agent(QueueClient([LLMResponse("not json")])).analyze(input_for())

    assert result.analysis_source is AnalysisSource.FALLBACK


def test_missing_field_uses_fallback() -> None:
    payload = json.loads(valid_payload())
    del payload["summary"]

    result = agent(QueueClient([LLMResponse(json.dumps(payload))])).analyze(input_for())

    assert result.analysis_source is AnalysisSource.FALLBACK


def test_wrong_incident_id_uses_fallback() -> None:
    result = agent(
        QueueClient([LLMResponse(valid_payload(incident_id="wrong"))])
    ).analyze(input_for())

    assert result.analysis_source is AnalysisSource.FALLBACK


def test_timeout_uses_fallback() -> None:
    result = agent(QueueClient([LLMTimeoutError("provider timed out")])).analyze(
        input_for()
    )

    assert result.analysis_source is AnalysisSource.FALLBACK
    assert any("超时" in warning for warning in result.warnings)


def test_provider_error_uses_fallback() -> None:
    result = agent(QueueClient([LLMProviderError("provider unavailable")])).analyze(
        input_for()
    )

    assert result.analysis_source is AnalysisSource.FALLBACK
    assert any("提供商" in warning for warning in result.warnings)


def test_single_repair_attempt() -> None:
    client = QueueClient(
        [LLMResponse("invalid"), LLMResponse(valid_payload(), model="repaired")]
    )

    result = agent(client, retries=1).analyze(input_for())

    assert result.analysis_source is AnalysisSource.LLM
    assert result.model == "repaired"
    assert len(client.calls) == 2
    assert "previous response was invalid" in client.calls[1][1].lower()


def test_fallback_active_severity() -> None:
    result = agent(None).analyze(input_for(IncidentStatus.ACTIVE))

    assert result.severity is Severity.SEV_3
    assert result.confidence < 0.5
    assert result.affected_services == ["Azure SQL"]
    assert "本地遥测" in result.potential_impact[0]


def test_fallback_resolved_severity() -> None:
    result = agent(None).analyze(input_for(IncidentStatus.RESOLVED))

    assert result.severity is Severity.SEV_4


def test_fallback_is_deterministic() -> None:
    decision_agent = agent(None)

    assert decision_agent.analyze(input_for()) == decision_agent.analyze(input_for())


def test_exhausted_repair_uses_fallback() -> None:
    client = QueueClient([LLMResponse("invalid one"), LLMResponse("invalid two")])

    result = agent(client, retries=1).analyze(input_for())

    assert result.analysis_source is AnalysisSource.FALLBACK
    assert len(client.calls) == 2
