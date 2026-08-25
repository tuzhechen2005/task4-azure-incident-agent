from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.models.schemas import (
    AgentInput,
    AnalysisSource,
    CycleResult,
    ErrorDetail,
    ErrorResponse,
    IncidentAnalysis,
    IncidentListResponse,
    IncidentRecord,
    IncidentStatus,
    NormalizedIncident,
    RawIncident,
    ResponsePlan,
    Severity,
    StatsResponse,
)

UTC_NOW = datetime(2026, 8, 25, 3, 0, tzinfo=timezone.utc)


def raw_incident(**overrides: object) -> RawIncident:
    values: dict[str, object] = {
        "source": "azure_status_rss",
        "source_url": "https://example.test/feed.xml",
        "source_event_id": "event-1",
        "title": " Azure SQL disruption ",
        "description": "Connections are failing.",
        "link": "https://example.test/incidents/1",
        "published_at": UTC_NOW,
        "fetched_at": UTC_NOW,
    }
    values.update(overrides)
    return RawIncident.model_validate(values)


def normalized_incident(**overrides: object) -> NormalizedIncident:
    values: dict[str, object] = {
        "incident_id": "inc-1",
        "title": "Azure SQL disruption",
        "description": "Connections are failing.",
        "services": ["Azure SQL"],
        "regions": ["East US"],
        "status": IncidentStatus.ACTIVE,
        "source": "azure_status_rss",
        "source_event_id": "event-1",
        "source_url": "https://example.test/feed.xml",
        "source_link": "https://example.test/incidents/1",
        "published_at": UTC_NOW,
        "detected_at": UTC_NOW,
        "updated_at": UTC_NOW,
        "content_fingerprint": "a" * 64,
    }
    values.update(overrides)
    return NormalizedIncident.model_validate(values)


def analysis(**overrides: object) -> IncidentAnalysis:
    values: dict[str, object] = {
        "incident_id": "inc-1",
        "severity": Severity.SEV_3,
        "confidence": 0.6,
        "affected_services": ["Azure SQL"],
        "affected_regions": ["East US"],
        "scope": "Some database connections may fail.",
        "summary": "Azure SQL connectivity is degraded.",
        "potential_impact": ["Intermittent query failures"],
        "recommended_actions": ["Check application telemetry"],
        "response_plan": ResponsePlan(
            immediate_actions=["Confirm impact"],
            investigation_steps=["Review metrics"],
            mitigation_options=[],
            communication_plan=["Update service owners"],
            recovery_checks=["Confirm error rate recovery"],
            escalation_conditions=["Escalate if impact expands"],
        ),
        "rationale": "The supplied entry reports limited degradation.",
        "analyzed_at": UTC_NOW,
        "analysis_source": AnalysisSource.FALLBACK,
        "model": None,
        "warnings": ["Low-confidence fallback"],
    }
    values.update(overrides)
    return IncidentAnalysis.model_validate(values)


def test_raw_incident_valid() -> None:
    incident = raw_incident()

    assert incident.title == "Azure SQL disruption"
    assert str(incident.source_url) == "https://example.test/feed.xml"
    assert incident.fetched_at == UTC_NOW


def test_normalized_incident_requires_utc_times() -> None:
    with pytest.raises(ValidationError, match="timezone-aware"):
        normalized_incident(detected_at=datetime(2026, 8, 25, 3, 0))

    converted = normalized_incident(
        detected_at=datetime(2026, 8, 25, 11, 0, tzinfo=timezone.utc)
    )
    assert converted.detected_at.tzinfo == timezone.utc


@pytest.mark.parametrize("severity", list(Severity))
def test_analysis_accepts_each_severity(severity: Severity) -> None:
    assert analysis(severity=severity).severity is severity


def test_analysis_rejects_invalid_confidence() -> None:
    with pytest.raises(ValidationError):
        analysis(confidence=1.01)


def test_analysis_incident_id_consistency() -> None:
    with pytest.raises(ValidationError, match="incident_id"):
        IncidentRecord(
            incident=normalized_incident(), analysis=analysis(incident_id="other")
        )


def test_response_plan_defaults_are_isolated() -> None:
    first = ResponsePlan()
    second = ResponsePlan()

    first.immediate_actions.append("one")

    assert second.immediate_actions == []


def test_schema_json_round_trip() -> None:
    record = IncidentRecord(incident=normalized_incident(), analysis=analysis())

    restored = IncidentRecord.model_validate_json(record.model_dump_json())

    assert restored == record
    assert '"severity":"SEV-3"' in record.model_dump_json()
    assert '"analyzed_at":"2026-08-25T03:00:00Z"' in record.model_dump_json()


def test_missing_required_field() -> None:
    with pytest.raises(ValidationError, match="title"):
        RawIncident.model_validate(
            {
                "source_url": "https://example.test/feed.xml",
                "description": "description",
                "fetched_at": UTC_NOW,
            }
        )


def test_agent_input_uses_only_analysis_fields() -> None:
    agent_input = AgentInput.from_incident(normalized_incident())

    assert set(agent_input.model_dump()) == {
        "incident_id",
        "title",
        "description",
        "services",
        "regions",
        "status",
        "published_at",
        "source_link",
    }


def test_list_stats_cycle_and_error_contracts_validate() -> None:
    record = IncidentRecord(incident=normalized_incident(), analysis=analysis())
    listing = IncidentListResponse(items=[record], page=1, page_size=20, total=1)
    stats = StatsResponse(
        total=1,
        status_counts={IncidentStatus.ACTIVE: 1},
        severity_counts={Severity.SEV_3: 1},
        latest_incident_at=UTC_NOW,
        last_ingestion_at=UTC_NOW,
        last_successful_ingestion_at=UTC_NOW,
    )
    cycle = CycleResult(started_at=UTC_NOW, ended_at=UTC_NOW, fetched_count=1)
    error = ErrorResponse(
        error=ErrorDetail(code="TEST", message="safe", request_id="r-1")
    )

    assert listing.total == stats.total == cycle.fetched_count == 1
    assert error.error.details is None


def test_string_lists_are_trimmed_and_deduplicated() -> None:
    incident = normalized_incident(services=[" Azure SQL ", "Azure SQL", ""])

    assert incident.services == ["Azure SQL"]
