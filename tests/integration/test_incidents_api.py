from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from app.api.app import create_app
from app.config import Settings
from app.models.schemas import (
    AnalysisSource,
    ErrorResponse,
    IncidentAnalysis,
    IncidentListResponse,
    IncidentRecord,
    IncidentStatus,
    NormalizedIncident,
    ResponsePlan,
    Severity,
)
from app.storage.database import Database
from app.storage.repository import IncidentRepository

NOW = datetime(2026, 8, 25, 11, 0, tzinfo=timezone.utc)


class FakeScheduler:
    is_started = False
    last_error = None
    last_run_at = NOW
    last_successful_run_at = NOW

    async def start(self) -> None:
        self.is_started = True

    async def stop(self) -> None:
        self.is_started = False


def repo(tmp_path: Path) -> IncidentRepository:
    result = IncidentRepository(Database(tmp_path / "api.db"))
    result.initialize()
    return result


def make_record(
    incident_id: str,
    *,
    offset: int,
    status: IncidentStatus = IncidentStatus.ACTIVE,
    severity: Severity = Severity.SEV_3,
    service: str = "Azure SQL",
    region: str = "East US",
) -> IncidentRecord:
    updated_at = NOW + timedelta(minutes=offset)
    incident = NormalizedIncident.model_validate(
        {
            "incident_id": incident_id,
            "title": f"Incident {incident_id}",
            "description": "Fixture incident details.",
            "services": [service],
            "regions": [region],
            "status": status,
            "source": "fixture",
            "source_url": "https://example.test/feed.xml",
            "source_link": f"https://example.test/incidents/{incident_id}",
            "published_at": updated_at,
            "detected_at": NOW,
            "updated_at": updated_at,
            "content_fingerprint": (incident_id + "0" * 64)[:64],
        }
    )
    return IncidentRecord(
        incident=incident,
        analysis=IncidentAnalysis(
            incident_id=incident_id,
            severity=severity,
            confidence=0.6,
            affected_services=[service],
            affected_regions=[region],
            scope="Fixture scope",
            summary="Fixture summary",
            potential_impact=["Possible errors"],
            recommended_actions=["Check telemetry"],
            response_plan=ResponsePlan(),
            rationale="Fixture rationale",
            analyzed_at=updated_at,
            analysis_source=AnalysisSource.FALLBACK,
            warnings=[],
        ),
    )


def app_client(repository: IncidentRepository) -> TestClient:
    settings = Settings.model_validate({"llm_api_key": "test-key"})
    return TestClient(
        create_app(settings=settings, repository=repository, scheduler=FakeScheduler())
    )


def seed(repository: IncidentRepository) -> None:
    repository.upsert(make_record("older", offset=0))
    repository.upsert(
        make_record(
            "newer",
            offset=10,
            status=IncidentStatus.RESOLVED,
            severity=Severity.SEV_4,
            service="Azure Storage",
            region="West Europe",
        )
    )
    repository.upsert(make_record("middle", offset=5, severity=Severity.SEV_2))


def test_list_incidents_empty(tmp_path: Path) -> None:
    with app_client(repo(tmp_path)) as client:
        response = client.get("/api/incidents")

    assert response.status_code == 200
    assert response.json() == {"items": [], "page": 1, "page_size": 20, "total": 0}


def test_list_incidents_default_order(tmp_path: Path) -> None:
    repository = repo(tmp_path)
    seed(repository)

    with app_client(repository) as client:
        payload = client.get("/api/incidents").json()

    assert [item["incident"]["incident_id"] for item in payload["items"]] == [
        "newer",
        "middle",
        "older",
    ]


def test_list_incidents_pagination(tmp_path: Path) -> None:
    repository = repo(tmp_path)
    seed(repository)

    with app_client(repository) as client:
        payload = client.get("/api/incidents?page=2&page_size=2").json()

    assert payload["total"] == 3
    assert payload["page"] == 2
    assert [item["incident"]["incident_id"] for item in payload["items"]] == ["older"]


def test_list_incidents_filter_severity(tmp_path: Path) -> None:
    repository = repo(tmp_path)
    seed(repository)

    with app_client(repository) as client:
        payload = client.get("/api/incidents?severity=SEV-2").json()

    assert [item["incident"]["incident_id"] for item in payload["items"]] == ["middle"]


def test_list_incidents_filter_status(tmp_path: Path) -> None:
    repository = repo(tmp_path)
    seed(repository)

    with app_client(repository) as client:
        payload = client.get("/api/incidents?status=RESOLVED").json()

    assert [item["incident"]["incident_id"] for item in payload["items"]] == ["newer"]


def test_list_incidents_filter_service_region(tmp_path: Path) -> None:
    repository = repo(tmp_path)
    seed(repository)

    with app_client(repository) as client:
        response = client.get(
            "/api/incidents?service=storage&region=west%20europe&status=RESOLVED&severity=SEV-4"
        )

    assert response.status_code == 200
    assert [item["incident"]["incident_id"] for item in response.json()["items"]] == [
        "newer"
    ]


def test_list_incidents_invalid_query(tmp_path: Path) -> None:
    with app_client(repo(tmp_path)) as client:
        responses = [
            client.get("/api/incidents?page=0"),
            client.get("/api/incidents?page_size=101"),
            client.get("/api/incidents?severity=SEV-9"),
            client.get("/api/incidents?status=BROKEN"),
        ]

    assert all(response.status_code == 422 for response in responses)


def test_get_incident(tmp_path: Path) -> None:
    repository = repo(tmp_path)
    expected = make_record("one", offset=0)
    repository.upsert(expected)

    with app_client(repository) as client:
        response = client.get("/api/incidents/one")

    assert response.status_code == 200
    assert IncidentRecord.model_validate(response.json()) == expected


def test_get_incident_not_found(tmp_path: Path) -> None:
    with app_client(repo(tmp_path)) as client:
        response = client.get("/api/incidents/missing")

    assert response.status_code == 404
    error = ErrorResponse.model_validate(response.json())
    assert error.error.code == "INCIDENT_NOT_FOUND"
    assert error.error.request_id == response.headers["x-request-id"]


def test_incident_response_schema(tmp_path: Path) -> None:
    repository = repo(tmp_path)
    seed(repository)

    with app_client(repository) as client:
        response = client.get("/api/incidents")

    parsed = IncidentListResponse.model_validate(response.json())
    assert parsed.total == 3
