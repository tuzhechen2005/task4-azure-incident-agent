"""Reliable RSS retrieval behind an injectable HTTP transport."""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

import httpx


class RSSFetchError(RuntimeError):
    """Base class for controlled RSS retrieval failures."""


class TimeoutFetchError(RSSFetchError):
    """The source did not respond before the configured timeout."""


class NetworkFetchError(RSSFetchError):
    """The source could not be reached due to a network failure."""


class HTTPStatusError(RSSFetchError):
    """The source returned a non-success HTTP status."""

    def __init__(self, status_code: int) -> None:
        self.status_code = status_code
        super().__init__(f"RSS source returned HTTP {status_code}")


class EmptyBodyError(RSSFetchError):
    """The source returned a success status with no feed content."""


@dataclass(frozen=True, slots=True)
class HTTPResponse:
    status_code: int
    body: bytes
    headers: Mapping[str, str]


@dataclass(frozen=True, slots=True)
class FetchResult:
    body: bytes
    source_url: str
    fetched_at: datetime
    status_code: int
    headers: dict[str, str]


class HTTPTransport(Protocol):
    """Minimal transport contract used by the RSS client."""

    def get(
        self, url: str, *, timeout: float, headers: dict[str, str]
    ) -> HTTPResponse: ...


class HTTPXTransport:
    """Verified HTTPS transport backed by the project's shared HTTP client."""

    def get(self, url: str, *, timeout: float, headers: dict[str, str]) -> HTTPResponse:
        try:
            response = httpx.get(
                url,
                timeout=timeout,
                headers=headers,
                follow_redirects=True,
            )
        except httpx.TimeoutException as error:
            raise TimeoutError("RSS request timed out") from error
        except httpx.RequestError as error:
            raise OSError("RSS network request failed") from error
        return HTTPResponse(
            status_code=response.status_code,
            body=response.content,
            headers=dict(response.headers),
        )


class RSSClient:
    """Fetch a feed with finite timeouts and deterministic bounded retries."""

    USER_AGENT = "azure-incident-agent/1.0"

    def __init__(
        self,
        *,
        url: str,
        timeout_seconds: float,
        max_retries: int,
        transport: HTTPTransport | None = None,
        clock: Callable[[], datetime] | None = None,
        sleeper: Callable[[float], None] | None = None,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if max_retries < 0:
            raise ValueError("max_retries must not be negative")
        self._url = url
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries
        self._transport = transport or HTTPXTransport()
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._sleeper = sleeper or time.sleep

    def fetch(self) -> FetchResult:
        """Return feed bytes and retrieval metadata or a controlled typed error."""
        for attempt in range(self._max_retries + 1):
            try:
                response = self._transport.get(
                    self._url,
                    timeout=self._timeout_seconds,
                    headers={
                        "User-Agent": self.USER_AGENT,
                        "Accept": "application/rss+xml, application/atom+xml, application/xml",
                    },
                )
            except TimeoutError as error:
                failure: RSSFetchError = TimeoutFetchError("RSS request timed out")
                if self._can_retry(attempt):
                    self._backoff(attempt)
                    continue
                raise failure from error
            except OSError as error:
                failure = NetworkFetchError("RSS network request failed")
                if self._can_retry(attempt):
                    self._backoff(attempt)
                    continue
                raise failure from error

            if not 200 <= response.status_code < 300:
                failure = HTTPStatusError(response.status_code)
                if self._is_retryable_status(response.status_code) and self._can_retry(
                    attempt
                ):
                    self._backoff(attempt)
                    continue
                raise failure

            if not response.body.strip():
                raise EmptyBodyError("RSS source returned an empty body")

            fetched_at = self._clock()
            if fetched_at.tzinfo is None or fetched_at.utcoffset() is None:
                raise ValueError("clock must return a timezone-aware datetime")
            return FetchResult(
                body=response.body,
                source_url=self._url,
                fetched_at=fetched_at.astimezone(timezone.utc),
                status_code=response.status_code,
                headers=dict(response.headers),
            )

        raise AssertionError("retry loop ended unexpectedly")

    def _can_retry(self, attempt: int) -> bool:
        return attempt < self._max_retries

    @staticmethod
    def _is_retryable_status(status_code: int) -> bool:
        return status_code == 429 or status_code >= 500

    def _backoff(self, attempt: int) -> None:
        self._sleeper(min(0.25 * (2**attempt), 1.0))
