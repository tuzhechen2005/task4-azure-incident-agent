from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone

import pytest

from app.ingestion.rss_client import (
    EmptyBodyError,
    HTTPResponse,
    HTTPStatusError,
    NetworkFetchError,
    RSSClient,
    TimeoutFetchError,
)

NOW = datetime(2026, 8, 25, 4, 0, tzinfo=timezone.utc)


class FakeTransport:
    def __init__(self, outcomes: Iterable[HTTPResponse | Exception]) -> None:
        self.outcomes = list(outcomes)
        self.calls: list[tuple[str, float, dict[str, str]]] = []

    def get(self, url: str, *, timeout: float, headers: dict[str, str]) -> HTTPResponse:
        self.calls.append((url, timeout, headers))
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def client(transport: FakeTransport, *, retries: int = 0) -> RSSClient:
    return RSSClient(
        url="https://example.test/feed.xml",
        timeout_seconds=4,
        max_retries=retries,
        transport=transport,
        clock=lambda: NOW,
        sleeper=lambda _: None,
    )


def test_fetch_valid_feed() -> None:
    body = b"<rss><channel /></rss>"
    transport = FakeTransport(
        [HTTPResponse(status_code=200, body=body, headers={"etag": "abc"})]
    )

    result = client(transport).fetch()

    assert result.body == body
    assert result.source_url == "https://example.test/feed.xml"
    assert result.fetched_at == NOW
    assert result.status_code == 200
    assert result.headers == {"etag": "abc"}
    assert transport.calls[0][1] == 4
    assert transport.calls[0][2]["User-Agent"].startswith("azure-incident-agent/")


def test_fetch_timeout() -> None:
    transport = FakeTransport([TimeoutError("socket timed out")])

    with pytest.raises(TimeoutFetchError, match="timed out"):
        client(transport).fetch()


def test_fetch_network_error() -> None:
    transport = FakeTransport([OSError("connection reset")])

    with pytest.raises(NetworkFetchError, match="network"):
        client(transport).fetch()


def test_fetch_http_error() -> None:
    transport = FakeTransport(
        [HTTPResponse(status_code=404, body=b"missing", headers={})]
    )

    with pytest.raises(HTTPStatusError) as error:
        client(transport).fetch()

    assert error.value.status_code == 404
    assert "missing" not in str(error.value)


def test_fetch_empty_body() -> None:
    transport = FakeTransport([HTTPResponse(status_code=200, body=b"  ", headers={})])

    with pytest.raises(EmptyBodyError, match="empty"):
        client(transport).fetch()


def test_fetch_retries_within_limit() -> None:
    transport = FakeTransport(
        [
            TimeoutError("first"),
            HTTPResponse(status_code=503, body=b"later", headers={}),
            HTTPResponse(status_code=200, body=b"<rss />", headers={}),
        ]
    )

    result = client(transport, retries=2).fetch()

    assert result.body == b"<rss />"
    assert len(transport.calls) == 3


def test_fetch_does_not_retry_nonretryable_error() -> None:
    transport = FakeTransport(
        [
            HTTPResponse(status_code=400, body=b"bad request", headers={}),
            HTTPResponse(status_code=200, body=b"<rss />", headers={}),
        ]
    )

    with pytest.raises(HTTPStatusError):
        client(transport, retries=2).fetch()

    assert len(transport.calls) == 1
