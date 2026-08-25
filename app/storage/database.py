"""SQLite connection and schema lifecycle management."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


class Database:
    """Own database path creation, connection defaults, and idempotent schema setup."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        try:
            yield connection
        finally:
            connection.close()

    def initialize(self) -> None:
        """Create the current schema safely if it is not already present."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS schema_metadata (
                    version INTEGER PRIMARY KEY,
                    applied_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS incidents (
                    incident_id TEXT PRIMARY KEY,
                    incident_json TEXT NOT NULL,
                    analysis_json TEXT NOT NULL,
                    content_fingerprint TEXT NOT NULL,
                    status TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    services_search TEXT NOT NULL,
                    regions_search TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    analyzed_at TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_incidents_updated
                    ON incidents(updated_at DESC, incident_id ASC);
                CREATE INDEX IF NOT EXISTS idx_incidents_status
                    ON incidents(status);
                CREATE INDEX IF NOT EXISTS idx_incidents_severity
                    ON incidents(severity);
                """
            )
            connection.execute(
                "INSERT OR IGNORE INTO schema_metadata(version, applied_at) VALUES (?, ?)",
                (1, datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")),
            )
            connection.commit()
