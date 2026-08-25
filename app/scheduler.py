"""Non-overlapping application-lifecycle ingestion scheduler."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Protocol

from app.models.schemas import CycleResult

LOGGER = logging.getLogger(__name__)


class CycleService(Protocol):
    def process_cycle(self) -> CycleResult: ...


class SchedulerWaiter(Protocol):
    async def wait(self, seconds: float, stop_event: asyncio.Event) -> bool: ...


class AsyncioWaiter:
    """Wait for either the configured interval or an early shutdown signal."""

    async def wait(self, seconds: float, stop_event: asyncio.Event) -> bool:
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=seconds)
        except TimeoutError:
            return False
        return True


class IngestionScheduler:
    """Run ingestion at startup and repeatedly without overlapping cycles."""

    def __init__(
        self,
        *,
        service: CycleService,
        interval_seconds: float,
        waiter: SchedulerWaiter | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be positive")
        self._service = service
        self._interval_seconds = interval_seconds
        self._waiter = waiter or AsyncioWaiter()
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task[None] | None = None
        self._cycle_running = False
        self.last_run_at: datetime | None = None
        self.last_successful_run_at: datetime | None = None
        self.last_result: CycleResult | None = None
        self.last_error: str | None = None
        self.overlap_skips = 0

    @property
    def is_started(self) -> bool:
        return self._task is not None and not self._task.done()

    @property
    def is_running(self) -> bool:
        return self._cycle_running

    async def start(self) -> None:
        """Run the startup cycle and launch the repeating background loop."""
        if self.is_started:
            return
        self._stop_event.clear()
        LOGGER.info("scheduler_started interval_seconds=%s", self._interval_seconds)
        await self.run_once()
        self._task = asyncio.create_task(self._run_loop(), name="incident-ingestion")

    async def stop(self) -> None:
        """Signal shutdown and wait for the scheduler loop to finish cleanly."""
        self._stop_event.set()
        if self._task is not None:
            await self._task
            self._task = None
        LOGGER.info("scheduler_stopped")

    async def wait_stopped(self) -> None:
        """Wait for an injected finite scheduler loop, primarily for deterministic tests."""
        if self._task is not None:
            await self._task

    async def run_once(self) -> CycleResult | None:
        """Run one cycle or record an overlap skip without raising cycle failures."""
        if self._cycle_running:
            self.overlap_skips += 1
            LOGGER.warning("scheduler_cycle_skipped reason=overlap")
            return None
        self._cycle_running = True
        try:
            result = await asyncio.to_thread(self._service.process_cycle)
            self.last_result = result
            self.last_run_at = self._now()
            if result.failed_count == 0:
                self.last_successful_run_at = self.last_run_at
                self.last_error = None
            else:
                self.last_error = "; ".join(result.errors) or "cycle reported failures"
                LOGGER.warning(
                    "scheduler_cycle_degraded failed=%d", result.failed_count
                )
            if result.failed_count == 0:
                LOGGER.info("scheduler_cycle_succeeded")
            return result
        except Exception as error:
            self.last_run_at = self._now()
            self.last_error = f"cycle failed ({type(error).__name__})"
            LOGGER.warning("scheduler_cycle_failed error_type=%s", type(error).__name__)
            return None
        finally:
            self._cycle_running = False

    async def _run_loop(self) -> None:
        while not await self._waiter.wait(self._interval_seconds, self._stop_event):
            await self.run_once()

    def _now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("clock must return a timezone-aware datetime")
        return value.astimezone(timezone.utc)
