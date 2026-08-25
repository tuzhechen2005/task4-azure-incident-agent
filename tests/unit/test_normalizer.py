from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.ingestion.normalizer import normalize_incident
from app.models.schemas import IncidentStatus, RawIncident

FETCHED = datetime(2026, 8, 25, 5, 0, tzinfo=timezone.utc)


def raw(**overrides: object) -> RawIncident:
    values: dict[str, object] = {
        "source": "azure_status_rss",
        "source_url": "https://example.test/feed.xml",
        "source_event_id": "EVT-100",
        "title": " Azure SQL degradation in East US ",
        "description": " We are investigating intermittent connection failures. ",
        "link": "https://example.test/incidents/100",
        "published_at": FETCHED - timedelta(minutes=5),
        "fetched_at": FETCHED,
    }
    values.update(overrides)
    return RawIncident.model_validate(values)


def test_normalize_complete_incident() -> None:
    incident = normalize_incident(raw())

    assert incident.title == "Azure SQL degradation in East US"
    assert incident.services == ["Azure SQL"]
    assert incident.regions == ["East US"]
    assert incident.status is IncidentStatus.ACTIVE
    assert incident.source_event_id == "EVT-100"
    assert len(incident.content_fingerprint) == 64


def test_normalize_missing_service_region() -> None:
    incident = normalize_incident(
        raw(title="Service notice", description="We are reviewing the report.")
    )

    assert incident.services == []
    assert incident.regions == []


def test_identity_prefers_source_event_id() -> None:
    first = normalize_incident(raw(title="Original title"))
    changed = normalize_incident(
        raw(title="Changed title", description="Different details")
    )

    assert first.incident_id == changed.incident_id


def test_identity_fallback_is_deterministic() -> None:
    first = normalize_incident(raw(source_event_id=None))
    repeated = normalize_incident(
        raw(source_event_id=None, fetched_at=FETCHED + timedelta(hours=1))
    )

    assert first.incident_id == repeated.incident_id


def test_content_change_changes_fingerprint_not_identity() -> None:
    first = normalize_incident(raw())
    changed = normalize_incident(raw(description="The incident impact has expanded."))

    assert first.incident_id == changed.incident_id
    assert first.content_fingerprint != changed.content_fingerprint


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("We are investigating an outage.", IncidentStatus.ACTIVE),
        ("Mitigation applied; we are monitoring recovery.", IncidentStatus.MONITORING),
        (
            "The incident has been resolved and service recovered.",
            IncidentStatus.RESOLVED,
        ),
        ("A general service notice is available.", IncidentStatus.UNKNOWN),
    ],
)
def test_status_mapping(text: str, expected: IncidentStatus) -> None:
    incident = normalize_incident(raw(title="Azure notice", description=text))

    assert incident.status is expected


def test_invalid_required_text() -> None:
    invalid = RawIncident.model_construct(
        source="azure_status_rss",
        source_url="https://example.test/feed.xml",
        source_event_id=None,
        title=" ",
        description="details",
        link=None,
        published_at=None,
        fetched_at=FETCHED,
    )

    with pytest.raises((ValidationError, ValueError), match="title"):
        normalize_incident(invalid)


def test_normalize_utc_timestamps() -> None:
    plus_eight = timezone(timedelta(hours=8))
    incident = normalize_incident(
        raw(
            published_at=datetime(2026, 8, 25, 12, 0, tzinfo=plus_eight),
            fetched_at=datetime(2026, 8, 25, 13, 0, tzinfo=plus_eight),
        )
    )

    assert incident.published_at == datetime(2026, 8, 25, 4, 0, tzinfo=timezone.utc)
    assert incident.detected_at == datetime(2026, 8, 25, 5, 0, tzinfo=timezone.utc)
    assert incident.updated_at.tzinfo == timezone.utc
