"""FastAPI application factory and dependency lifecycle wiring."""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles

from app.agents.decision_agent import DecisionAgent
from app.api.errors import (
    ApplicationError,
    application_error_handler,
    unexpected_error_handler,
)
from app.config import Settings
from app.ingestion.rss_client import RSSClient
from app.scheduler import IngestionScheduler
from app.services.incident_service import IncidentService
from app.storage.database import Database
from app.storage.repository import IncidentRepository


class RepositoryLifecycle(Protocol):
    def initialize(self) -> None: ...


class SchedulerLifecycle(Protocol):
    async def start(self) -> None: ...

    async def stop(self) -> None: ...


def _default_dependencies(
    settings: Settings,
) -> tuple[IncidentRepository, IngestionScheduler]:
    repository = IncidentRepository(Database(settings.database_path))
    fetcher = RSSClient(
        url=str(settings.azure_status_rss_url),
        timeout_seconds=settings.rss_timeout_seconds,
        max_retries=settings.rss_max_retries,
    )
    agent = DecisionAgent(
        client=None,
        timeout_seconds=settings.llm_timeout_seconds,
        max_retries=settings.llm_max_retries,
    )
    service = IncidentService(fetcher=fetcher, repository=repository, agent=agent)
    scheduler = IngestionScheduler(
        service=service,
        interval_seconds=settings.ingestion_interval_seconds,
    )
    return repository, scheduler


def create_app(
    *,
    settings: Settings | None = None,
    repository: RepositoryLifecycle | None = None,
    scheduler: SchedulerLifecycle | None = None,
) -> FastAPI:
    """Create an app with fully injectable persistence and scheduling dependencies."""
    resolved_settings = settings or Settings()
    if repository is None or scheduler is None:
        default_repository, default_scheduler = _default_dependencies(resolved_settings)
        repository = repository or default_repository
        scheduler = scheduler or default_scheduler

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        del application
        repository.initialize()
        await scheduler.start()
        try:
            yield
        finally:
            await scheduler.stop()

    application = FastAPI(
        title="Azure Incident Response Agent",
        version="1.0.0",
        lifespan=lifespan,
    )
    application.state.settings = resolved_settings
    application.state.repository = repository
    application.state.scheduler = scheduler

    @application.middleware("http")
    async def request_id_middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = request.headers.get("X-Request-ID", "").strip() or str(uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    application.add_exception_handler(ApplicationError, application_error_handler)  # type: ignore[arg-type]
    application.add_exception_handler(Exception, unexpected_error_handler)

    frontend_directory = Path(__file__).resolve().parents[2] / "frontend"
    application.mount(
        "/static",
        StaticFiles(directory=frontend_directory, check_dir=False),
        name="static",
    )
    return application
