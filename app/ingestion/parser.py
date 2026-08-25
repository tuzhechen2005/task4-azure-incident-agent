"""Defensive RSS/Atom parsing with per-entry isolation."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser

from pydantic import ValidationError

from app.models.schemas import RawIncident


class FeedParseError(ValueError):
    """The supplied bytes are not a structurally valid XML feed."""


@dataclass(slots=True)
class ParseResult:
    incidents: list[RawIncident] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class _PlainTextExtractor(HTMLParser):
    """Extract visible text while discarding executable/style element content."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._ignored_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        normalized_tag = tag.lower()
        if normalized_tag in {"script", "style"}:
            self._ignored_depth += 1
        elif (
            normalized_tag in {"br", "div", "li", "p", "tr"} and not self._ignored_depth
        ):
            self.parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        normalized_tag = tag.lower()
        if normalized_tag in {"script", "style"} and self._ignored_depth:
            self._ignored_depth -= 1
        elif normalized_tag in {"div", "li", "p", "tr"} and not self._ignored_depth:
            self.parts.append(" ")

    def handle_data(self, data: str) -> None:
        if not self._ignored_depth:
            self.parts.append(data)


def _plain_text(value: str) -> str:
    extractor = _PlainTextExtractor()
    extractor.feed(value)
    extractor.close()
    return " ".join("".join(extractor.parts).split())


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def _child(element: ET.Element, *names: str) -> ET.Element | None:
    accepted = {name.lower() for name in names}
    return next(
        (child for child in element if _local_name(child.tag) in accepted),
        None,
    )


def _content(element: ET.Element | None) -> str:
    if element is None:
        return ""
    return _plain_text("".join(element.itertext()))


def _parse_datetime(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _entry_link(element: ET.Element) -> str | None:
    link = _child(element, "link")
    if link is None:
        return None
    value = link.attrib.get("href") or _content(link)
    return value or None


def _parse_entry(
    element: ET.Element,
    *,
    source: str,
    source_url: str,
    fetched_at: datetime,
) -> RawIncident:
    published_text = _content(_child(element, "pubdate", "published", "updated"))
    return RawIncident.model_validate(
        {
            "source": source,
            "source_url": source_url,
            "source_event_id": _content(_child(element, "guid", "id")) or None,
            "title": _content(_child(element, "title")),
            "description": _content(
                _child(element, "description", "summary", "content")
            ),
            "link": _entry_link(element),
            "published_at": _parse_datetime(published_text),
            "fetched_at": fetched_at,
        }
    )


def parse_feed(
    body: bytes,
    *,
    source_url: str,
    fetched_at: datetime,
    source: str = "azure_status_rss",
) -> ParseResult:
    """Parse supplied RSS/Atom bytes and preserve valid siblings of bad entries."""
    try:
        root = ET.fromstring(body)
    except (ET.ParseError, ValueError) as error:
        raise FeedParseError("Invalid XML feed") from error

    root_type = _local_name(root.tag)
    if root_type not in {"rss", "rdf", "feed"}:
        raise FeedParseError(f"Unsupported feed root: {root_type}")

    entries = [
        element
        for element in root.iter()
        if _local_name(element.tag) in {"item", "entry"}
    ]
    result = ParseResult()
    for index, entry in enumerate(entries, start=1):
        try:
            result.incidents.append(
                _parse_entry(
                    entry,
                    source=source,
                    source_url=source_url,
                    fetched_at=fetched_at,
                )
            )
        except (ValidationError, ValueError) as error:
            result.warnings.append(f"Skipped malformed entry {index}: {error}")
    return result
