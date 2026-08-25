"""One-cycle incident ingestion, deduplication, analysis, and persistence."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Protocol

from app.ingestion.normalizer import normalize_incident
from app.ingestion.parser import parse_feed
from app.ingestion.rss_client import FetchResult
from app.models.schemas import (
    AgentInput,
    CycleResult,
    IncidentAnalysis,
    IncidentRecord,
)
from app.storage.repository import IncidentRepository


class FeedFetcher(Protocol):
    def fetch(self) -> FetchResult: ...


class IncidentAnalyzer(Protocol):
    def analyze(self, agent_input: AgentInput) -> IncidentAnalysis: ...


class IncidentService:
    """Process valid entries independently while preserving existing records on failure."""

    def __init__(
        self,
        *,
        fetcher: FeedFetcher,
        repository: IncidentRepository,
        agent: IncidentAnalyzer,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._fetcher = fetcher
        self._repository = repository
        self._agent = agent
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def process_cycle(self) -> CycleResult:
        """Run one complete cycle and return safe, exact processing counts."""
        started_at = self._now()
        fetched_count = 0
        parsed_count = 0
        inserted_count = 0
        updated_count = 0
        unchanged_count = 0
        failed_count = 0
        errors: list[str] = []

        try:
            fetched = self._fetcher.fetch()
            parsed = parse_feed(
                fetched.body,
                source_url=fetched.source_url,
                fetched_at=fetched.fetched_at,
            )
        except Exception as error:
            return CycleResult(
                started_at=started_at,
                ended_at=self._now(),
                failed_count=1,
                errors=[self._safe_error("feed", error)],
            )

        parsed_count = len(parsed.incidents)
        fetched_count = parsed_count + len(parsed.warnings)
        failed_count = len(parsed.warnings)
        if parsed.warnings:
            errors.append(
                f"Skipped {len(parsed.warnings)} malformed feed entry/entries"
            )

        for raw_incident in parsed.incidents:
            try:
                incident = normalize_incident(raw_incident)
                existing = self._repository.get(incident.incident_id)
                if (
                    existing is not None
                    and existing.incident.content_fingerprint
                    == incident.content_fingerprint
                ):
                    unchanged_count += 1
                    continue

                if existing is not None:
                    incident = incident.model_copy(
                        update={"detected_at": existing.incident.detected_at}
                    )
                analysis = self._agent.analyze(AgentInput.from_incident(incident))
                self._repository.upsert(
                    IncidentRecord(incident=incident, analysis=analysis)
                )
                if existing is None:
                    inserted_count += 1
                else:
                    updated_count += 1
            except Exception as error:
                failed_count += 1
                errors.append(self._safe_error("entry", error))

        return CycleResult(
            started_at=started_at,
            ended_at=self._now(),
            fetched_count=fetched_count,
            parsed_count=parsed_count,
            inserted_count=inserted_count,
            updated_count=updated_count,
            unchanged_count=unchanged_count,
            failed_count=failed_count,
            errors=errors,
        )

    def _now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("clock must return a timezone-aware datetime")
        return value.astimezone(timezone.utc)

    @staticmethod
    def _safe_error(stage: str, error: Exception) -> str:
        return f"{stage} processing failed ({type(error).__name__})"
