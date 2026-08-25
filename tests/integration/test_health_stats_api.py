from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.api.app import create_app
from app.config import Settings
from app.models.schemas import (
    AnalysisSource,
    HealthResponse,
    IncidentAnalysis,
    IncidentRecord,
    IncidentStatus,
    NormalizedIncident,
    ResponsePlan,
    Severity,
    StatsResponse,
)
from app.storage.database import Database
from app.storage.repository import IncidentRepository

NOW = datetime(2026, 8, 25, 10, 0, tzinfo=timezone.utc)


class FakeScheduler:
    def __init__(self, *, last_error: str | None = None) -> None:
        self.is_started = False
        self.last_error = last_error
        self.last_run_at: datetime | None = NOW
        self.last_successful_run_at: datetime | None = None if last_error else NOW

    async def start(self) -> None:
        self.is_started = True

    async def stop(self) -> None:
        self.is_started = False


class UnavailableRepository:
    def initialize(self) -> None:
        return None

    def stats(self, **kwargs: object) -> StatsResponse:
        del kwargs
        raise OSError("secret database location")


def app_settings(*, fallback: bool) -> Settings:
    return Settings.model_validate(
        {"llm_api_key": SecretStr("") if fallback else SecretStr("test-only-key")}
    )


def repository(tmp_path: Path) -> IncidentRepository:
    repo = IncidentRepository(Database(tmp_path / "health.db"))
    repo.initialize()
    return repo


def record(
    incident_id: str, status: IncidentStatus, severity: Severity
) -> IncidentRecord:
    incident = NormalizedIncident.model_validate(
        {
            "incident_id": incident_id,
            "title": f"Incident {incident_id}",
            "description": "Controlled test incident.",
            "services": ["Azure SQL"],
            "regions": ["East US"],
            "status": status,
            "source": "fixture",
            "source_url": "https://example.test/feed.xml",
            "detected_at": NOW,
            "updated_at": NOW,
            "content_fingerprint": incident_id * 8,
        }
    )
    analysis = IncidentAnalysis(
        incident_id=incident_id,
        severity=severity,
        confidence=0.5,
        affected_services=incident.services,
        affected_regions=incident.regions,
        scope="Test scope",
        summary="Test summary",
        potential_impact=[],
        recommended_actions=[],
        response_plan=ResponsePlan(),
        rationale="Test rationale",
        analyzed_at=NOW,
        analysis_source=AnalysisSource.FALLBACK,
        warnings=[],
    )
    return IncidentRecord(incident=incident, analysis=analysis)


def test_health_healthy(tmp_path: Path) -> None:
    app = create_app(
        settings=app_settings(fallback=False),
        repository=repository(tmp_path),
        scheduler=FakeScheduler(),
    )

    with TestClient(app) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
    assert response.json()["database"] == "available"


def test_health_degraded_rss(tmp_path: Path) -> None:
    app = create_app(
        settings=app_settings(fallback=False),
        repository=repository(tmp_path),
        scheduler=FakeScheduler(
            last_error="feed processing failed (NetworkFetchError)"
        ),
    )

    with TestClient(app) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "degraded"
    assert "NetworkFetchError" in response.json()["last_error"]


def test_health_fallback_analysis_mode(tmp_path: Path) -> None:
    app = create_app(
        settings=app_settings(fallback=True),
        repository=repository(tmp_path),
        scheduler=FakeScheduler(),
    )

    with TestClient(app) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "degraded"
    assert response.json()["analysis_mode"] == "fallback-only"


def test_health_database_unavailable() -> None:
    app = create_app(
        settings=app_settings(fallback=False),
        repository=UnavailableRepository(),
        scheduler=FakeScheduler(),
    )

    with TestClient(app) as client:
        response = client.get("/api/health")

    assert response.status_code == 503
    assert response.json()["database"] == "unavailable"
    assert "secret database location" not in response.text


def test_stats_empty(tmp_path: Path) -> None:
    app = create_app(
        settings=app_settings(fallback=False),
        repository=repository(tmp_path),
        scheduler=FakeScheduler(),
    )

    with TestClient(app) as client:
        response = client.get("/api/stats")

    assert response.status_code == 200
    assert response.json()["total"] == 0
    assert response.json()["status_counts"] == {}
    assert response.json()["severity_counts"] == {}


def test_stats_seeded_counts(tmp_path: Path) -> None:
    repo = repository(tmp_path)
    repo.upsert(record("one", IncidentStatus.ACTIVE, Severity.SEV_2))
    repo.upsert(record("two", IncidentStatus.RESOLVED, Severity.SEV_4))
    app = create_app(
        settings=app_settings(fallback=False),
        repository=repo,
        scheduler=FakeScheduler(),
    )

    with TestClient(app) as client:
        payload = client.get("/api/stats").json()

    assert payload["total"] == 2
    assert payload["status_counts"] == {"ACTIVE": 1, "RESOLVED": 1}
    assert payload["severity_counts"] == {"SEV-2": 1, "SEV-4": 1}


def test_stats_latest_timestamps(tmp_path: Path) -> None:
    app = create_app(
        settings=app_settings(fallback=False),
        repository=repository(tmp_path),
        scheduler=FakeScheduler(),
    )

    with TestClient(app) as client:
        payload = client.get("/api/stats").json()

    assert payload["last_ingestion_at"] == "2026-08-25T10:00:00Z"
    assert payload["last_successful_ingestion_at"] == "2026-08-25T10:00:00Z"


def test_health_response_schema(tmp_path: Path) -> None:
    app = create_app(
        settings=app_settings(fallback=False),
        repository=repository(tmp_path),
        scheduler=FakeScheduler(),
    )

    with TestClient(app) as client:
        response = client.get("/api/health")

    assert HealthResponse.model_validate(response.json()).status == "healthy"
