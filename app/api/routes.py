"""Local monitoring health and statistics API routes."""

from __future__ import annotations

from typing import Annotated, Protocol, cast

from fastapi import APIRouter, Path, Query, Request
from fastapi.responses import JSONResponse

from app.api.errors import ApplicationError
from app.config import Settings
from app.models.schemas import (
    HealthResponse,
    IncidentListResponse,
    IncidentRecord,
    IncidentStatus,
    Severity,
    StatsResponse,
)


class StatsRepository(Protocol):
    def stats(
        self,
        *,
        last_ingestion_at: object = None,
        last_successful_ingestion_at: object = None,
    ) -> StatsResponse: ...

    def list_records(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        severity: Severity | None = None,
        status: IncidentStatus | None = None,
        service: str | None = None,
        region: str | None = None,
    ) -> IncidentListResponse: ...

    def get(self, incident_id: str) -> IncidentRecord | None: ...


router = APIRouter(prefix="/api")


@router.get("/health", response_model=HealthResponse)
def health(request: Request) -> JSONResponse:
    repository = cast(StatsRepository, request.app.state.repository)
    scheduler = request.app.state.scheduler
    settings = cast(Settings, request.app.state.settings)
    scheduler_started = bool(getattr(scheduler, "is_started", False))
    scheduler_error = getattr(scheduler, "last_error", None)
    last_run = getattr(scheduler, "last_run_at", None)
    last_success = getattr(scheduler, "last_successful_run_at", None)

    try:
        repository.stats()
        database_state = "available"
        database_available = True
    except Exception:
        database_state = "unavailable"
        database_available = False

    analysis_mode = "fallback-only" if settings.fallback_only else settings.llm_provider
    degraded = (
        not database_available
        or not scheduler_started
        or bool(scheduler_error)
        or settings.fallback_only
    )
    payload = HealthResponse(
        status="degraded" if degraded else "healthy",
        database=database_state,
        scheduler="running" if scheduler_started else "stopped",
        analysis_mode=analysis_mode,
        last_ingestion_at=last_run,
        last_successful_ingestion_at=last_success,
        last_error=(
            "database unavailable"
            if not database_available
            else str(scheduler_error)
            if scheduler_error
            else None
        ),
    )
    return JSONResponse(
        status_code=200 if database_available else 503,
        content=payload.model_dump(mode="json"),
    )


@router.get("/stats", response_model=StatsResponse)
def stats(request: Request) -> StatsResponse:
    repository = cast(StatsRepository, request.app.state.repository)
    scheduler = request.app.state.scheduler
    try:
        return repository.stats(
            last_ingestion_at=getattr(scheduler, "last_run_at", None),
            last_successful_ingestion_at=getattr(
                scheduler, "last_successful_run_at", None
            ),
        )
    except Exception as error:
        raise ApplicationError(
            code="DATABASE_UNAVAILABLE",
            message="Stored incident statistics are temporarily unavailable.",
            status_code=503,
        ) from error


@router.get("/incidents", response_model=IncidentListResponse)
def list_incidents(
    request: Request,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    severity: Severity | None = None,
    status: IncidentStatus | None = None,
    service: Annotated[str | None, Query(min_length=1, max_length=100)] = None,
    region: Annotated[str | None, Query(min_length=1, max_length=100)] = None,
) -> IncidentListResponse:
    repository = cast(StatsRepository, request.app.state.repository)
    try:
        return repository.list_records(
            page=page,
            page_size=page_size,
            severity=severity,
            status=status,
            service=service,
            region=region,
        )
    except Exception as error:
        raise ApplicationError(
            code="DATABASE_UNAVAILABLE",
            message="Stored incidents are temporarily unavailable.",
            status_code=503,
        ) from error


@router.get("/incidents/{incident_id}", response_model=IncidentRecord)
def get_incident(
    request: Request,
    incident_id: Annotated[str, Path(min_length=1, max_length=200)],
) -> IncidentRecord:
    repository = cast(StatsRepository, request.app.state.repository)
    try:
        record = repository.get(incident_id)
    except Exception as error:
        raise ApplicationError(
            code="DATABASE_UNAVAILABLE",
            message="Stored incidents are temporarily unavailable.",
            status_code=503,
        ) from error
    if record is None:
        raise ApplicationError(
            code="INCIDENT_NOT_FOUND",
            message="The requested incident was not found.",
            status_code=404,
        )
    return record
