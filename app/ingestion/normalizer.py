"""Conservative incident normalization, identity, and change detection."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from app.models.schemas import IncidentStatus, NormalizedIncident, RawIncident

_SERVICE_NAMES = (
    "Azure SQL",
    "Azure Storage",
    "Azure Kubernetes Service",
    "Azure App Service",
    "Azure Functions",
    "Azure Cosmos DB",
    "Azure Active Directory",
    "Virtual Machines",
)

_REGION_NAMES = (
    "East US",
    "East US 2",
    "West US",
    "West US 2",
    "West US 3",
    "Central US",
    "North Central US",
    "South Central US",
    "West Central US",
    "North Europe",
    "West Europe",
    "Southeast Asia",
    "East Asia",
    "UK South",
    "UK West",
    "Japan East",
    "Japan West",
    "Australia East",
    "Australia Southeast",
    "Canada Central",
    "Canada East",
)


def _clean_text(value: str, *, field_name: str) -> str:
    cleaned = " ".join(value.split())
    if not cleaned:
        raise ValueError(f"{field_name} must not be blank")
    return cleaned


def _extract_known_names(text: str, candidates: tuple[str, ...]) -> list[str]:
    lowered = text.casefold()
    found = [
        (lowered.find(candidate.casefold()), candidate)
        for candidate in candidates
        if candidate.casefold() in lowered
    ]
    return [candidate for _, candidate in sorted(found)]


def _derive_status(text: str) -> IncidentStatus:
    lowered = text.casefold()
    if any(word in lowered for word in ("resolved", "recovered", "restored")):
        return IncidentStatus.RESOLVED
    if any(
        phrase in lowered
        for phrase in ("monitoring", "mitigation applied", "recovering")
    ):
        return IncidentStatus.MONITORING
    if any(
        word in lowered
        for word in (
            "active",
            "degradation",
            "disruption",
            "failing",
            "failure",
            "impact",
            "investigating",
            "outage",
            "unavailable",
        )
    ):
        return IncidentStatus.ACTIVE
    return IncidentStatus.UNKNOWN


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("incident timestamps must be timezone-aware")
    return value.astimezone(timezone.utc)


def _hash_payload(payload: dict[str, object]) -> str:
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def normalize_incident(raw: RawIncident) -> NormalizedIncident:
    """Normalize one parsed entry without inventing unsupported facts."""
    title = _clean_text(raw.title, field_name="title")
    description = _clean_text(raw.description, field_name="description")
    combined_text = f"{title}\n{description}"
    services = _extract_known_names(combined_text, _SERVICE_NAMES)
    regions = _extract_known_names(combined_text, _REGION_NAMES)
    status = _derive_status(combined_text)
    published_at = _utc(raw.published_at) if raw.published_at else None
    fetched_at = _utc(raw.fetched_at)

    if raw.source_event_id:
        identity_material: dict[str, object] = {
            "source": raw.source,
            "source_event_id": raw.source_event_id,
        }
    else:
        identity_material = {
            "source": raw.source,
            "title": title.casefold(),
            "published_at": published_at.isoformat() if published_at else None,
            "source_link": str(raw.link) if raw.link else None,
        }
    incident_id = f"inc_{_hash_payload(identity_material)[:32]}"

    fingerprint = _hash_payload(
        {
            "title": title,
            "description": description,
            "services": services,
            "regions": regions,
            "status": status.value,
            "published_at": published_at.isoformat() if published_at else None,
        }
    )

    return NormalizedIncident.model_validate(
        {
            "incident_id": incident_id,
            "title": title,
            "description": description,
            "services": services,
            "regions": regions,
            "status": status,
            "source": raw.source,
            "source_event_id": raw.source_event_id,
            "source_url": raw.source_url,
            "source_link": raw.link,
            "published_at": published_at,
            "detected_at": fetched_at,
            "updated_at": published_at or fetched_at,
            "content_fingerprint": fingerprint,
        }
    )
