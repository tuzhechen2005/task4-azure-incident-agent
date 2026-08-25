from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.agents.decision_agent import DecisionAgent
from app.ingestion.rss_client import FetchResult, NetworkFetchError
from app.models.schemas import AgentInput, IncidentAnalysis
from app.services.incident_service import IncidentService
from app.storage.database import Database
from app.storage.repository import IncidentRepository

NOW = datetime(2026, 8, 25, 8, 0, tzinfo=timezone.utc)


def rss(*items: tuple[str, str, str]) -> bytes:
    entries = "".join(
        f"<item><guid>{event_id}</guid><title>{title}</title>"
        f"<description>{description}</description>"
        f"<pubDate>Tue, 25 Aug 2026 08:00:00 +0000</pubDate></item>"
        for event_id, title, description in items
    )
    return f"<rss><channel>{entries}</channel></rss>".encode()


class FakeFetcher:
    def __init__(self, outcomes: list[FetchResult | Exception]) -> None:
        self.outcomes = outcomes

    def fetch(self) -> FetchResult:
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class CountingAgent:
    def __init__(self) -> None:
        self.calls: list[AgentInput] = []
        self.fallback = DecisionAgent(
            client=None, timeout_seconds=1, max_retries=0, clock=lambda: NOW
        )

    def analyze(self, agent_input: AgentInput) -> IncidentAnalysis:
        self.calls.append(agent_input)
        return self.fallback.analyze(agent_input)


class IncrementingClock:
    def __init__(self) -> None:
        self.current = NOW

    def __call__(self) -> datetime:
        value = self.current
        self.current += timedelta(seconds=1)
        return value


def fetch_result(body: bytes) -> FetchResult:
    return FetchResult(
        body=body,
        source_url="https://example.test/feed.xml",
        fetched_at=NOW,
        status_code=200,
        headers={},
    )


@pytest.fixture
def repository(tmp_path: Path) -> IncidentRepository:
    repo = IncidentRepository(Database(tmp_path / "service.db"))
    repo.initialize()
    return repo


def service(
    repository: IncidentRepository,
    outcomes: list[FetchResult | Exception],
    agent: CountingAgent | None = None,
) -> tuple[IncidentService, CountingAgent]:
    counting_agent = agent or CountingAgent()
    return (
        IncidentService(
            fetcher=FakeFetcher(outcomes),
            repository=repository,
            agent=counting_agent,
            clock=IncrementingClock(),
        ),
        counting_agent,
    )


def test_process_new_incident(repository: IncidentRepository) -> None:
    processor, agent = service(
        repository,
        [fetch_result(rss(("one", "Azure SQL outage", "Connections are failing.")))],
    )

    cycle = processor.process_cycle()

    assert cycle.inserted_count == 1
    assert cycle.failed_count == 0
    assert len(agent.calls) == 1
    assert repository.list_records().total == 1


def test_process_multiple_incidents(repository: IncidentRepository) -> None:
    body = rss(
        ("one", "Azure SQL outage", "Connections are failing."),
        ("two", "Azure Storage resolved", "Service recovered."),
    )
    processor, agent = service(repository, [fetch_result(body)])

    cycle = processor.process_cycle()

    assert cycle.parsed_count == 2
    assert cycle.inserted_count == 2
    assert len(agent.calls) == 2


def test_unchanged_incident_skips_agent(repository: IncidentRepository) -> None:
    result = fetch_result(rss(("one", "Azure SQL outage", "Connections are failing.")))
    agent = CountingAgent()
    processor, _ = service(repository, [result, result], agent)

    first = processor.process_cycle()
    second = processor.process_cycle()

    assert first.inserted_count == 1
    assert second.unchanged_count == 1
    assert len(agent.calls) == 1


def test_changed_incident_reanalyzes(repository: IncidentRepository) -> None:
    original = fetch_result(
        rss(("one", "Azure SQL outage", "Connections are failing."))
    )
    changed = fetch_result(rss(("one", "Azure SQL outage", "Impact has expanded.")))
    agent = CountingAgent()
    processor, _ = service(repository, [original, changed], agent)

    processor.process_cycle()
    cycle = processor.process_cycle()

    assert cycle.updated_count == 1
    assert len(agent.calls) == 2
    assert repository.list_records().total == 1


def test_entry_failure_does_not_abort_cycle(repository: IncidentRepository) -> None:
    body = b"""<rss><channel>
    <item><guid>bad</guid><title> </title><description>bad</description></item>
    <item><guid>good</guid><title>Valid outage</title><description>Impact reported.</description></item>
    </channel></rss>"""
    processor, _ = service(repository, [fetch_result(body)])

    cycle = processor.process_cycle()

    assert cycle.inserted_count == 1
    assert cycle.failed_count == 1
    assert repository.list_records().total == 1


def test_fetch_failure_preserves_storage(repository: IncidentRepository) -> None:
    first, _ = service(
        repository,
        [fetch_result(rss(("one", "Azure SQL outage", "Connections are failing.")))],
    )
    first.process_cycle()
    failing, _ = service(repository, [NetworkFetchError("offline")])

    cycle = failing.process_cycle()

    assert cycle.failed_count == 1
    assert repository.list_records().total == 1


def test_empty_feed_cycle(repository: IncidentRepository) -> None:
    processor, agent = service(repository, [fetch_result(b"<rss><channel /></rss>")])

    cycle = processor.process_cycle()

    assert cycle.fetched_count == 0
    assert cycle.parsed_count == 0
    assert len(agent.calls) == 0


def test_cycle_result_counts(repository: IncidentRepository) -> None:
    initial = fetch_result(
        rss(
            ("same", "Azure SQL outage", "Connections are failing."),
            ("change", "Storage issue", "Impact reported."),
        )
    )
    next_feed = fetch_result(
        rss(
            ("same", "Azure SQL outage", "Connections are failing."),
            ("change", "Storage issue", "Impact expanded."),
            ("new", "Compute issue", "VM impact reported."),
        )
    )
    processor, _ = service(repository, [initial, next_feed])
    processor.process_cycle()

    cycle = processor.process_cycle()

    assert cycle.fetched_count == 3
    assert cycle.parsed_count == 3
    assert cycle.inserted_count == 1
    assert cycle.updated_count == 1
    assert cycle.unchanged_count == 1
    assert cycle.failed_count == 0
    assert cycle.ended_at > cycle.started_at


def test_atomic_service_update(
    repository: IncidentRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = fetch_result(
        rss(("one", "Azure SQL outage", "Connections are failing."))
    )
    changed = fetch_result(rss(("one", "Azure SQL outage", "Impact expanded.")))
    processor, _ = service(repository, [original, changed])
    processor.process_cycle()
    stored_before = repository.list_records().items[0]

    monkeypatch.setattr(
        repository, "upsert", lambda _: (_ for _ in ()).throw(OSError("disk"))
    )
    cycle = processor.process_cycle()

    assert cycle.failed_count == 1
    assert repository.get(stored_before.incident.incident_id) == stored_before


def test_logs_safe_stage_summaries_without_exception_details(
    caplog: pytest.LogCaptureFixture,
    repository: IncidentRepository,
) -> None:
    secret = "secret-provider-token"
    processor, _ = service(repository, [RuntimeError(secret)])

    with caplog.at_level(logging.INFO):
        result = processor.process_cycle()

    assert result.failed_count == 1
    assert "ingestion_cycle_started" in caplog.text
    assert "feed_fetch_failed error_type=RuntimeError" in caplog.text
    assert secret not in caplog.text
