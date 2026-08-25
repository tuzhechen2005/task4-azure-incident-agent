from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.ingestion.parser import FeedParseError, parse_feed

FIXTURES = Path(__file__).parents[1] / "fixtures"
FETCHED_AT = datetime(2026, 8, 25, 4, 5, tzinfo=timezone.utc)
SOURCE_URL = "https://example.test/feed.xml"


def fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def test_parse_valid_feed() -> None:
    result = parse_feed(
        fixture("rss_valid.xml"), source_url=SOURCE_URL, fetched_at=FETCHED_AT
    )

    assert len(result.incidents) == 2
    first = result.incidents[0]
    assert first.source_event_id == "event-100"
    assert first.title == "Azure SQL degradation"
    assert first.description == "Connections are intermittently failing."
    assert str(first.link) == "https://example.test/incidents/100"
    assert first.fetched_at == FETCHED_AT
    assert result.warnings == []


def test_parse_atom_variant() -> None:
    atom = b"""<?xml version='1.0'?>
    <feed xmlns='http://www.w3.org/2005/Atom'>
      <entry><id>atom-1</id><title>Compute notice</title>
      <summary>Some VMs are restarting.</summary>
      <link href='https://example.test/atom/1'/>
      <updated>2026-08-25T12:00:00+08:00</updated></entry>
    </feed>"""

    result = parse_feed(atom, source_url=SOURCE_URL, fetched_at=FETCHED_AT)

    assert result.incidents[0].source_event_id == "atom-1"
    assert result.incidents[0].description == "Some VMs are restarting."
    assert result.incidents[0].published_at == datetime(
        2026, 8, 25, 4, 0, tzinfo=timezone.utc
    )


def test_parse_empty_feed() -> None:
    result = parse_feed(
        fixture("rss_empty.xml"), source_url=SOURCE_URL, fetched_at=FETCHED_AT
    )

    assert result.incidents == []
    assert result.warnings == []


def test_parse_invalid_xml() -> None:
    with pytest.raises(FeedParseError, match="Invalid XML"):
        parse_feed(b"<rss><broken>", source_url=SOURCE_URL, fetched_at=FETCHED_AT)


def test_parse_skips_malformed_entry() -> None:
    result = parse_feed(
        fixture("rss_malformed_entry.xml"),
        source_url=SOURCE_URL,
        fetched_at=FETCHED_AT,
    )

    assert [incident.source_event_id for incident in result.incidents] == ["good-1"]
    assert len(result.warnings) == 1
    assert "entry 1" in result.warnings[0]


def test_parse_missing_optional_fields() -> None:
    rss = b"""<rss><channel><item><title>Notice</title>
    <description>Details available.</description></item></channel></rss>"""

    incident = parse_feed(rss, source_url=SOURCE_URL, fetched_at=FETCHED_AT).incidents[
        0
    ]

    assert incident.source_event_id is None
    assert incident.link is None
    assert incident.published_at is None


def test_parse_description_as_plain_text() -> None:
    rss = b"""<rss><channel><item><title>Unsafe sample</title>
    <description>&lt;script&gt;alert('x')&lt;/script&gt;&lt;p&gt;Safe &amp;amp; useful&lt;/p&gt;</description>
    </item></channel></rss>"""

    description = (
        parse_feed(rss, source_url=SOURCE_URL, fetched_at=FETCHED_AT)
        .incidents[0]
        .description
    )

    assert "<script>" not in description
    assert "alert" not in description
    assert description == "Safe & useful"


def test_parse_timezone_to_utc() -> None:
    incident = parse_feed(
        fixture("rss_valid.xml"), source_url=SOURCE_URL, fetched_at=FETCHED_AT
    ).incidents[0]

    assert incident.published_at == datetime(2026, 8, 25, 3, 30, tzinfo=timezone.utc)
