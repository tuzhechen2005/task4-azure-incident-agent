from __future__ import annotations

import asyncio
import threading
from datetime import datetime, timedelta, timezone

from app.models.schemas import CycleResult
from app.scheduler import IngestionScheduler

NOW = datetime(2026, 8, 25, 9, 0, tzinfo=timezone.utc)


def cycle(*, failed: int = 0) -> CycleResult:
    return CycleResult(
        started_at=NOW,
        ended_at=NOW + timedelta(seconds=1),
        fetched_count=1,
        parsed_count=1,
        inserted_count=1 if not failed else 0,
        failed_count=failed,
        errors=["controlled failure"] if failed else [],
    )


class OutcomeService:
    def __init__(self, outcomes: list[CycleResult | Exception]) -> None:
        self.outcomes = outcomes
        self.calls = 0

    def process_cycle(self) -> CycleResult:
        self.calls += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class StopImmediatelyWaiter:
    async def wait(self, seconds: float, stop_event: asyncio.Event) -> bool:
        del seconds, stop_event
        return True


class OneIntervalWaiter:
    def __init__(self) -> None:
        self.calls = 0

    async def wait(self, seconds: float, stop_event: asyncio.Event) -> bool:
        del stop_event
        assert seconds == 30
        self.calls += 1
        return self.calls > 1


class UntilStoppedWaiter:
    async def wait(self, seconds: float, stop_event: asyncio.Event) -> bool:
        del seconds
        await stop_event.wait()
        return True


class BlockingService:
    def __init__(self) -> None:
        self.started = threading.Event()
        self.release = threading.Event()
        self.calls = 0

    def process_cycle(self) -> CycleResult:
        self.calls += 1
        self.started.set()
        assert self.release.wait(timeout=2)
        return cycle()


def scheduler(
    service: OutcomeService | BlockingService,
    *,
    waiter: StopImmediatelyWaiter
    | OneIntervalWaiter
    | UntilStoppedWaiter
    | None = None,
) -> IngestionScheduler:
    return IngestionScheduler(
        service=service,
        interval_seconds=30,
        waiter=waiter or StopImmediatelyWaiter(),
        clock=lambda: NOW,
    )


def test_runs_once_on_startup() -> None:
    async def scenario() -> None:
        service = OutcomeService([cycle()])
        instance = scheduler(service)

        await instance.start()
        await instance.wait_stopped()

        assert service.calls == 1

    asyncio.run(scenario())


def test_runs_at_configured_interval() -> None:
    async def scenario() -> None:
        service = OutcomeService([cycle(), cycle()])
        instance = scheduler(service, waiter=OneIntervalWaiter())

        await instance.start()
        await instance.wait_stopped()

        assert service.calls == 2

    asyncio.run(scenario())


def test_prevents_overlapping_cycles() -> None:
    async def scenario() -> None:
        service = BlockingService()
        instance = scheduler(service)
        first = asyncio.create_task(instance.run_once())
        await asyncio.to_thread(service.started.wait, 2)

        overlapping = await instance.run_once()
        service.release.set()
        await first

        assert overlapping is None
        assert instance.overlap_skips == 1
        assert service.calls == 1

    asyncio.run(scenario())


def test_cycle_exception_does_not_stop_scheduler() -> None:
    async def scenario() -> None:
        service = OutcomeService([RuntimeError("boom"), cycle()])
        instance = scheduler(service)

        first = await instance.run_once()
        second = await instance.run_once()

        assert first is None
        assert second is not None
        assert service.calls == 2
        assert instance.last_error is None

    asyncio.run(scenario())


def test_records_last_success() -> None:
    async def scenario() -> None:
        service = OutcomeService([cycle(failed=1), cycle()])
        instance = scheduler(service)

        await instance.run_once()
        assert instance.last_run_at == NOW
        assert instance.last_successful_run_at is None
        assert instance.last_error == "controlled failure"

        await instance.run_once()
        assert instance.last_successful_run_at == NOW
        assert instance.last_error is None

    asyncio.run(scenario())


def test_graceful_shutdown() -> None:
    async def scenario() -> None:
        service = OutcomeService([cycle()])
        instance = scheduler(service, waiter=UntilStoppedWaiter())

        await instance.start()
        await instance.stop()

        assert instance.is_started is False
        assert instance.is_running is False

    asyncio.run(scenario())
