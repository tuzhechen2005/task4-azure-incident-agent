from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from app.agents.decision_agent import DecisionAgent
from app.api.app import create_app
from app.config import Settings
from app.ingestion.rss_client import FetchResult
from app.models.schemas import AgentInput, IncidentAnalysis
from app.services.incident_service import IncidentService
from app.storage.database import Database
from app.storage.repository import IncidentRepository

NOW = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)
FIXTURE = Path(__file__).parents[1] / "fixtures" / "rss_valid.xml"


class FixtureFetcher:
    def __init__(self, body: bytes) -> None:
        self.body = body

    def fetch(self) -> FetchResult:
        return FetchResult(
            body=self.body,
            source_url="https://example.test/feed.xml",
            fetched_at=NOW,
            status_code=200,
            headers={},
        )


class CountingFallbackAgent:
    def __init__(self) -> None:
        self.calls = 0
        self.agent = DecisionAgent(
            client=None, timeout_seconds=1, max_retries=0, clock=lambda: NOW
        )

    def analyze(self, value: AgentInput) -> IncidentAnalysis:
        self.calls += 1
        return self.agent.analyze(value)


class PassiveScheduler:
    is_started = False
    last_error = None
    last_run_at = NOW
    last_successful_run_at = NOW

    async def start(self) -> None:
        self.is_started = True

    async def stop(self) -> None:
        self.is_started = False


def repository(path: Path) -> IncidentRepository:
    repo = IncidentRepository(Database(path))
    repo.initialize()
    return repo


def process(repo: IncidentRepository, agent: CountingFallbackAgent) -> None:
    IncidentService(
        fetcher=FixtureFetcher(FIXTURE.read_bytes()),
        repository=repo,
        agent=agent,
        clock=lambda: NOW,
    ).process_cycle()


def application(repo: IncidentRepository, *, poll_seconds: int = 30):
    settings = Settings.model_validate(
        {"dashboard_poll_seconds": poll_seconds, "llm_api_key": "test-key"}
    )
    return create_app(settings=settings, repository=repo, scheduler=PassiveScheduler())


def test_fixture_feed_to_api(tmp_path: Path) -> None:
    repo = repository(tmp_path / "pipeline.db")
    process(repo, CountingFallbackAgent())

    with TestClient(application(repo)) as client:
        listing = client.get("/api/incidents")
        stats = client.get("/api/stats")

    assert listing.status_code == 200
    assert listing.json()["total"] == 2
    assert stats.json()["total"] == 2


def test_fallback_feed_to_api(tmp_path: Path) -> None:
    repo = repository(tmp_path / "fallback.db")
    process(repo, CountingFallbackAgent())

    with TestClient(application(repo)) as client:
        payload = client.get("/api/incidents").json()

    assert all(
        item["analysis"]["analysis_source"] == "FALLBACK" for item in payload["items"]
    )


def test_duplicate_end_to_end(tmp_path: Path) -> None:
    repo = repository(tmp_path / "duplicate.db")
    agent = CountingFallbackAgent()

    process(repo, agent)
    process(repo, agent)

    assert repo.list_records().total == 2
    assert agent.calls == 2


def test_restart_persistence(tmp_path: Path) -> None:
    path = tmp_path / "restart.db"
    process(repository(path), CountingFallbackAgent())

    reopened = repository(path)
    with TestClient(application(reopened)) as client:
        response = client.get("/api/incidents")

    assert response.json()["total"] == 2


def test_dashboard_receives_configured_poll_interval(tmp_path: Path) -> None:
    with TestClient(
        application(repository(tmp_path / "dashboard.db"), poll_seconds=17)
    ) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert 'content="17"' in response.text
    assert "/static/app.js" in response.text
