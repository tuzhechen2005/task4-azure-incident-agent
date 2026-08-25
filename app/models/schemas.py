"""Canonical validated schemas shared by ingestion, storage, agents, and API."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Any, Self

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    HttpUrl,
    field_validator,
    model_validator,
)


def _clean_string_list(value: object) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, (list, tuple)):
        raise ValueError("value must be a list of strings")
    result: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise ValueError("list entries must be strings")
        cleaned = " ".join(item.split())
        if cleaned and cleaned not in result:
            result.append(cleaned)
    return result


CleanStringList = Annotated[list[str], BeforeValidator(_clean_string_list)]


class IncidentStatus(str, Enum):
    ACTIVE = "ACTIVE"
    MONITORING = "MONITORING"
    RESOLVED = "RESOLVED"
    UNKNOWN = "UNKNOWN"


class Severity(str, Enum):
    SEV_1 = "SEV-1"
    SEV_2 = "SEV-2"
    SEV_3 = "SEV-3"
    SEV_4 = "SEV-4"


class AnalysisSource(str, Enum):
    LLM = "LLM"
    FALLBACK = "FALLBACK"


class SchemaModel(BaseModel):
    """Strict base model with normalized strings and UTC datetimes."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        str_min_length=1,
        validate_assignment=True,
    )

    @field_validator("*", mode="after")
    @classmethod
    def require_utc_datetimes(cls, value: Any) -> Any:
        if isinstance(value, datetime):
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError("datetime must be timezone-aware")
            return value.astimezone(timezone.utc)
        return value


class RawIncident(SchemaModel):
    source: str = "azure_status_rss"
    source_url: HttpUrl
    source_event_id: str | None = None
    title: str
    description: str
    link: HttpUrl | None = None
    published_at: datetime | None = None
    fetched_at: datetime


class NormalizedIncident(SchemaModel):
    incident_id: str
    title: str
    description: str
    services: CleanStringList = Field(default_factory=list)
    regions: CleanStringList = Field(default_factory=list)
    status: IncidentStatus
    source: str
    source_event_id: str | None = None
    source_url: HttpUrl
    source_link: HttpUrl | None = None
    published_at: datetime | None = None
    detected_at: datetime
    updated_at: datetime
    content_fingerprint: str


class AgentInput(SchemaModel):
    incident_id: str
    title: str
    description: str
    services: CleanStringList = Field(default_factory=list)
    regions: CleanStringList = Field(default_factory=list)
    status: IncidentStatus
    published_at: datetime | None = None
    source_link: HttpUrl | None = None

    @classmethod
    def from_incident(cls, incident: NormalizedIncident) -> Self:
        """Create the intentionally narrow analysis input contract."""
        return cls.model_validate(
            incident.model_dump(
                include={
                    "incident_id",
                    "title",
                    "description",
                    "services",
                    "regions",
                    "status",
                    "published_at",
                    "source_link",
                }
            )
        )


class ResponsePlan(SchemaModel):
    immediate_actions: CleanStringList = Field(default_factory=list)
    investigation_steps: CleanStringList = Field(default_factory=list)
    mitigation_options: CleanStringList = Field(default_factory=list)
    communication_plan: CleanStringList = Field(default_factory=list)
    recovery_checks: CleanStringList = Field(default_factory=list)
    escalation_conditions: CleanStringList = Field(default_factory=list)


class IncidentAnalysis(SchemaModel):
    incident_id: str
    severity: Severity
    confidence: float = Field(ge=0, le=1)
    affected_services: CleanStringList = Field(default_factory=list)
    affected_regions: CleanStringList = Field(default_factory=list)
    scope: str
    summary: str
    potential_impact: CleanStringList = Field(default_factory=list)
    recommended_actions: CleanStringList = Field(default_factory=list)
    response_plan: ResponsePlan
    rationale: str
    analyzed_at: datetime
    analysis_source: AnalysisSource
    model: str | None = None
    warnings: CleanStringList = Field(default_factory=list)


class IncidentRecord(SchemaModel):
    incident: NormalizedIncident
    analysis: IncidentAnalysis

    @model_validator(mode="after")
    def validate_incident_id_consistency(self) -> Self:
        if self.incident.incident_id != self.analysis.incident_id:
            raise ValueError("incident_id must match between incident and analysis")
        return self


class IncidentListResponse(SchemaModel):
    items: list[IncidentRecord] = Field(default_factory=list)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    total: int = Field(ge=0)


class StatsResponse(SchemaModel):
    total: int = Field(default=0, ge=0)
    status_counts: dict[IncidentStatus, int] = Field(default_factory=dict)
    severity_counts: dict[Severity, int] = Field(default_factory=dict)
    latest_incident_at: datetime | None = None
    last_ingestion_at: datetime | None = None
    last_successful_ingestion_at: datetime | None = None


class CycleResult(SchemaModel):
    started_at: datetime
    ended_at: datetime
    fetched_count: int = Field(default=0, ge=0)
    parsed_count: int = Field(default=0, ge=0)
    inserted_count: int = Field(default=0, ge=0)
    updated_count: int = Field(default=0, ge=0)
    unchanged_count: int = Field(default=0, ge=0)
    failed_count: int = Field(default=0, ge=0)
    errors: CleanStringList = Field(default_factory=list)


class ErrorDetail(SchemaModel):
    code: str
    message: str
    details: dict[str, Any] | None = None
    request_id: str


class ErrorResponse(SchemaModel):
    error: ErrorDetail


class HealthResponse(SchemaModel):
    status: str
    database: str
    scheduler: str
    analysis_mode: str
    last_ingestion_at: datetime | None = None
    last_successful_ingestion_at: datetime | None = None
    last_error: str | None = None
