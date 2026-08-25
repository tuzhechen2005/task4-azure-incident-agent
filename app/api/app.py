"""FastAPI application factory and dependency lifecycle wiring."""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.agents.decision_agent import DecisionAgent
from app.api.errors import (
    ApplicationError,
    application_error_handler,
    unexpected_error_handler,
)
from app.api.routes import router as api_router
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
    uses_bundled_fallback = scheduler is None
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
        title="Azure 事件响应智能体",
        version="1.0.0",
        lifespan=lifespan,
    )
    application.state.settings = resolved_settings
    application.state.repository = repository
    application.state.scheduler = scheduler
    application.state.analysis_mode = (
        "fallback-only"
        if uses_bundled_fallback or resolved_settings.fallback_only
        else resolved_settings.llm_provider
    )

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
    application.include_router(api_router)

    frontend_directory = Path(__file__).resolve().parents[2] / "frontend"

    @application.get("/", response_class=HTMLResponse, include_in_schema=False)
    def dashboard() -> HTMLResponse:
        template = (frontend_directory / "index.html").read_text(encoding="utf-8")
        content = template.replace(
            "__DASHBOARD_POLL_SECONDS__",
            str(resolved_settings.dashboard_poll_seconds),
        )
        return HTMLResponse(content)

    application.mount(
        "/static",
        StaticFiles(directory=frontend_directory, check_dir=False),
        name="static",
    )
    return application
