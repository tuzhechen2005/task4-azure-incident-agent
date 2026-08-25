"""Seed a local SQLite database from the deterministic Azure RSS fixture."""

from __future__ import annotations

import argparse
import logging
from datetime import datetime, timezone
from pathlib import Path

from app.agents.decision_agent import DecisionAgent
from app.ingestion.rss_client import FetchResult
from app.services.incident_service import IncidentService
from app.storage.database import Database
from app.storage.repository import IncidentRepository

LOGGER = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "rss_valid.xml"


class FixtureFetcher:
    """Return bundled fixture bytes without any network access."""

    def fetch(self) -> FetchResult:
        return FetchResult(
            body=FIXTURE.read_bytes(),
            source_url="https://example.test/azure-status-fixture.xml",
            fetched_at=datetime.now(timezone.utc),
            status_code=200,
            headers={},
        )


def seed(database_path: Path) -> int:
    """Process the fixture once and return the number of stored records."""
    repository = IncidentRepository(Database(database_path))
    repository.initialize()
    agent = DecisionAgent(client=None, timeout_seconds=1, max_retries=0)
    result = IncidentService(
        fetcher=FixtureFetcher(),
        repository=repository,
        agent=agent,
    ).process_cycle()
    if result.failed_count:
        raise RuntimeError("Offline fixture ingestion failed")
    return repository.stats().total


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database",
        type=Path,
        default=Path("data/demo.db"),
        help="SQLite output path (default: data/demo.db)",
    )
    arguments = parser.parse_args()
    total = seed(arguments.database)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    LOGGER.info("Offline demo database ready: %s stored incidents", total)


if __name__ == "__main__":
    main()
