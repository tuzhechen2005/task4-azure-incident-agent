from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.routing import Mount

from app.api.app import create_app
from app.api.errors import ApplicationError
from app.config import Settings


class FakeRepository:
    def __init__(self) -> None:
        self.initialized = False

    def initialize(self) -> None:
        self.initialized = True


class FakeScheduler:
    def __init__(self) -> None:
        self.started = False
        self.stopped = False

    async def start(self) -> None:
        self.started = True

    async def stop(self) -> None:
        self.stopped = True


def settings() -> Settings:
    return Settings(_env_file=None)  # type: ignore[call-arg]


def test_app_startup_and_shutdown() -> None:
    repository = FakeRepository()
    scheduler = FakeScheduler()
    app = create_app(settings=settings(), repository=repository, scheduler=scheduler)

    with TestClient(app):
        assert repository.initialized is True
        assert scheduler.started is True

    assert scheduler.stopped is True


def test_app_uses_injected_dependencies() -> None:
    repository = FakeRepository()
    scheduler = FakeScheduler()
    app = create_app(settings=settings(), repository=repository, scheduler=scheduler)

    assert app.state.repository is repository
    assert app.state.scheduler is scheduler


def test_request_id_present_on_error() -> None:
    app = create_app(
        settings=settings(), repository=FakeRepository(), scheduler=FakeScheduler()
    )

    async def fail() -> None:
        raise ApplicationError(
            code="CONFLICT", message="Safe conflict", status_code=409
        )

    app.add_api_route("/api/fail", fail)
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/api/fail")

    assert response.status_code == 409
    assert response.headers["x-request-id"]
    assert response.json()["error"] == {
        "code": "CONFLICT",
        "message": "Safe conflict",
        "details": None,
        "request_id": response.headers["x-request-id"],
    }


def test_unhandled_error_is_sanitized() -> None:
    app = create_app(
        settings=settings(), repository=FakeRepository(), scheduler=FakeScheduler()
    )

    async def fail() -> None:
        raise RuntimeError("top-secret internal detail")

    app.add_api_route("/api/crash", fail)
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/api/crash")

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    assert "top-secret" not in response.text
    assert "traceback" not in response.text.lower()


def test_static_mount_does_not_shadow_api() -> None:
    app: FastAPI = create_app(
        settings=settings(), repository=FakeRepository(), scheduler=FakeScheduler()
    )

    async def api_route() -> dict[str, bool]:
        return {"ok": True}

    app.add_api_route("/api/example", api_route)
    with TestClient(app) as client:
        response = client.get("/api/example")

    assert response.json() == {"ok": True}
    assert any(
        isinstance(route, Mount) and route.path == "/static" for route in app.routes
    )
