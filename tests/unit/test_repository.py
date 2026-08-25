from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.models.schemas import (
    AnalysisSource,
    IncidentAnalysis,
    IncidentRecord,
    IncidentStatus,
    NormalizedIncident,
    ResponsePlan,
    Severity,
)
from app.storage.database import Database
from app.storage.repository import IncidentRepository

NOW = datetime(2026, 8, 25, 6, 0, tzinfo=timezone.utc)


def make_record(
    incident_id: str = "inc-1",
    *,
    status: IncidentStatus = IncidentStatus.ACTIVE,
    severity: Severity = Severity.SEV_3,
    updated_at: datetime = NOW,
    title: str = "Azure SQL degradation",
    services: list[str] | None = None,
    regions: list[str] | None = None,
    fingerprint: str = "a" * 64,
) -> IncidentRecord:
    incident = NormalizedIncident.model_validate(
        {
            "incident_id": incident_id,
            "title": title,
            "description": "Database connections are failing.",
            "services": services if services is not None else ["Azure SQL"],
            "regions": regions if regions is not None else ["East US"],
            "status": status,
            "source": "azure_status_rss",
            "source_event_id": incident_id,
            "source_url": "https://example.test/feed.xml",
            "source_link": f"https://example.test/incidents/{incident_id}",
            "published_at": updated_at,
            "detected_at": NOW,
            "updated_at": updated_at,
            "content_fingerprint": fingerprint,
        }
    )
    analysis = IncidentAnalysis(
        incident_id=incident_id,
        severity=severity,
        confidence=0.5,
        affected_services=incident.services,
        affected_regions=incident.regions,
        scope="Potential workload impact.",
        summary="A service incident is being tracked.",
        potential_impact=["Requests may fail"],
        recommended_actions=["Check telemetry"],
        response_plan=ResponsePlan(),
        rationale="Conservative assessment.",
        analyzed_at=updated_at,
        analysis_source=AnalysisSource.FALLBACK,
        warnings=[],
    )
    return IncidentRecord(incident=incident, analysis=analysis)


@pytest.fixture
def repository(tmp_path: Path) -> IncidentRepository:
    database = Database(tmp_path / "incidents.db")
    database.initialize()
    return IncidentRepository(database)


def test_initialize_database(tmp_path: Path) -> None:
    database = Database(tmp_path / "nested" / "incidents.db")

    database.initialize()

    with database.connect() as connection:
        tables = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    assert {row[0] for row in tables} >= {"incidents", "schema_metadata"}


def test_insert_and_get_record(repository: IncidentRepository) -> None:
    record = make_record()

    created = repository.upsert(record)

    assert created is True
    assert repository.get("inc-1") == record


def test_persistence_after_reopen(tmp_path: Path) -> None:
    path = tmp_path / "persistent.db"
    first = IncidentRepository(Database(path))
    first.initialize()
    first.upsert(make_record())

    reopened = IncidentRepository(Database(path))
    reopened.initialize()

    assert reopened.get("inc-1") == make_record()


def test_unique_incident_id(repository: IncidentRepository) -> None:
    repository.upsert(make_record())

    created = repository.upsert(make_record())

    assert created is False
    assert repository.list_records().total == 1


def test_atomic_upsert_rollback(repository: IncidentRepository) -> None:
    valid = make_record()
    repository.upsert(valid)
    invalid = IncidentRecord.model_construct(
        incident=valid.incident,
        analysis=valid.analysis.model_copy(update={"incident_id": "wrong"}),
    )

    with pytest.raises(ValidationError, match="incident_id"):
        repository.upsert(invalid)

    assert repository.get("inc-1") == valid


def test_update_changed_record(repository: IncidentRepository) -> None:
    repository.upsert(make_record())
    changed = make_record(
        title="Azure SQL recovered",
        status=IncidentStatus.RESOLVED,
        severity=Severity.SEV_4,
        fingerprint="b" * 64,
        updated_at=NOW + timedelta(minutes=5),
    )

    created = repository.upsert(changed)

    assert created is False
    assert repository.get("inc-1") == changed
    assert repository.list_records().total == 1


def test_list_empty(repository: IncidentRepository) -> None:
    result = repository.list_records()

    assert result.items == []
    assert result.total == 0
    assert result.page == 1


def test_list_filters_and_order(repository: IncidentRepository) -> None:
    repository.upsert(make_record("older", updated_at=NOW))
    repository.upsert(
        make_record(
            "newer",
            status=IncidentStatus.RESOLVED,
            severity=Severity.SEV_4,
            services=["Azure Storage"],
            regions=["West Europe"],
            updated_at=NOW + timedelta(minutes=10),
        )
    )

    assert [r.incident.incident_id for r in repository.list_records().items] == [
        "newer",
        "older",
    ]
    filtered = repository.list_records(
        severity=Severity.SEV_4,
        status=IncidentStatus.RESOLVED,
        service="storage",
        region="west europe",
    )
    assert [r.incident.incident_id for r in filtered.items] == ["newer"]


def test_pagination_total(repository: IncidentRepository) -> None:
    for index in range(3):
        repository.upsert(
            make_record(f"inc-{index}", updated_at=NOW + timedelta(minutes=index))
        )

    result = repository.list_records(page=2, page_size=2)

    assert result.total == 3
    assert [item.incident.incident_id for item in result.items] == ["inc-0"]


def test_stats_counts(repository: IncidentRepository) -> None:
    repository.upsert(make_record("active", severity=Severity.SEV_2))
    repository.upsert(
        make_record(
            "resolved",
            status=IncidentStatus.RESOLVED,
            severity=Severity.SEV_4,
            updated_at=NOW + timedelta(minutes=2),
        )
    )

    stats = repository.stats()

    assert stats.total == 2
    assert stats.status_counts == {
        IncidentStatus.ACTIVE: 1,
        IncidentStatus.RESOLVED: 1,
    }
    assert stats.severity_counts == {Severity.SEV_2: 1, Severity.SEV_4: 1}
    assert stats.latest_incident_at == NOW + timedelta(minutes=2)


def test_get_missing_incident(repository: IncidentRepository) -> None:
    assert repository.get("does-not-exist") is None


def test_invalid_json_is_rejected_on_read(
    repository: IncidentRepository, tmp_path: Path
) -> None:
    del tmp_path
    repository.upsert(make_record())
    with repository.database.connect() as connection:
        connection.execute(
            "UPDATE incidents SET analysis_json = ? WHERE incident_id = ?",
            ("{}", "inc-1"),
        )
        connection.commit()

    with pytest.raises(ValidationError):
        repository.get("inc-1")
