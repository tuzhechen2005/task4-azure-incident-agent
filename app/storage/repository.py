"""Validated atomic persistence and query operations for incident records."""

from __future__ import annotations

import sqlite3
from datetime import datetime

from app.models.schemas import (
    IncidentAnalysis,
    IncidentListResponse,
    IncidentRecord,
    IncidentStatus,
    NormalizedIncident,
    Severity,
    StatsResponse,
)
from app.storage.database import Database


class IncidentRepository:
    """Persist the latest validated incident and analysis as one atomic row."""

    def __init__(self, database: Database) -> None:
        self.database = database

    def initialize(self) -> None:
        self.database.initialize()

    @staticmethod
    def _validate_record(record: IncidentRecord) -> IncidentRecord:
        return IncidentRecord.model_validate(record.model_dump(mode="json"))

    def upsert(self, record: IncidentRecord) -> bool:
        """Atomically insert or replace one record; return whether it was new."""
        validated = self._validate_record(record)
        incident = validated.incident
        analysis = validated.analysis
        with self.database.connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                exists = connection.execute(
                    "SELECT 1 FROM incidents WHERE incident_id = ?",
                    (incident.incident_id,),
                ).fetchone()
                connection.execute(
                    """
                    INSERT INTO incidents (
                        incident_id, incident_json, analysis_json, content_fingerprint,
                        status, severity, services_search, regions_search,
                        updated_at, analyzed_at, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(incident_id) DO UPDATE SET
                        incident_json = excluded.incident_json,
                        analysis_json = excluded.analysis_json,
                        content_fingerprint = excluded.content_fingerprint,
                        status = excluded.status,
                        severity = excluded.severity,
                        services_search = excluded.services_search,
                        regions_search = excluded.regions_search,
                        updated_at = excluded.updated_at,
                        analyzed_at = excluded.analyzed_at
                    """,
                    (
                        incident.incident_id,
                        incident.model_dump_json(),
                        analysis.model_dump_json(),
                        incident.content_fingerprint,
                        incident.status.value,
                        analysis.severity.value,
                        "\n".join(item.casefold() for item in incident.services),
                        "\n".join(item.casefold() for item in incident.regions),
                        self._json_datetime(incident.updated_at),
                        self._json_datetime(analysis.analyzed_at),
                        self._json_datetime(incident.detected_at),
                    ),
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return exists is None

    def get(self, incident_id: str) -> IncidentRecord | None:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT incident_json, analysis_json FROM incidents WHERE incident_id = ?",
                (incident_id,),
            ).fetchone()
        return self._row_to_record(row) if row else None

    def list_records(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        severity: Severity | None = None,
        status: IncidentStatus | None = None,
        service: str | None = None,
        region: str | None = None,
    ) -> IncidentListResponse:
        if page < 1:
            raise ValueError("page must be positive")
        if not 1 <= page_size <= 100:
            raise ValueError("page_size must be between 1 and 100")
        where: list[str] = []
        parameters: list[object] = []
        if severity is not None:
            where.append("severity = ?")
            parameters.append(severity.value)
        if status is not None:
            where.append("status = ?")
            parameters.append(status.value)
        if service:
            where.append("services_search LIKE ?")
            parameters.append(f"%{service.strip().casefold()}%")
        if region:
            where.append("regions_search LIKE ?")
            parameters.append(f"%{region.strip().casefold()}%")
        clause = f" WHERE {' AND '.join(where)}" if where else ""

        with self.database.connect() as connection:
            total = connection.execute(
                f"SELECT COUNT(*) FROM incidents{clause}",  # noqa: S608
                parameters,
            ).fetchone()[0]
            rows = connection.execute(
                f"""SELECT incident_json, analysis_json FROM incidents{clause}
                    ORDER BY updated_at DESC, incident_id ASC LIMIT ? OFFSET ?""",  # noqa: S608
                [*parameters, page_size, (page - 1) * page_size],
            ).fetchall()
        return IncidentListResponse(
            items=[self._row_to_record(row) for row in rows],
            page=page,
            page_size=page_size,
            total=total,
        )

    def stats(
        self,
        *,
        last_ingestion_at: datetime | None = None,
        last_successful_ingestion_at: datetime | None = None,
    ) -> StatsResponse:
        with self.database.connect() as connection:
            total, latest = connection.execute(
                "SELECT COUNT(*), MAX(updated_at) FROM incidents"
            ).fetchone()
            status_rows = connection.execute(
                "SELECT status, COUNT(*) FROM incidents GROUP BY status"
            ).fetchall()
            severity_rows = connection.execute(
                "SELECT severity, COUNT(*) FROM incidents GROUP BY severity"
            ).fetchall()
        return StatsResponse.model_validate(
            {
                "total": total,
                "status_counts": {
                    IncidentStatus(row[0]): row[1] for row in status_rows
                },
                "severity_counts": {Severity(row[0]): row[1] for row in severity_rows},
                "latest_incident_at": latest,
                "last_ingestion_at": last_ingestion_at,
                "last_successful_ingestion_at": last_successful_ingestion_at,
            }
        )

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> IncidentRecord:
        incident = NormalizedIncident.model_validate_json(row["incident_json"])
        analysis = IncidentAnalysis.model_validate_json(row["analysis_json"])
        return IncidentRecord(incident=incident, analysis=analysis)

    @staticmethod
    def _json_datetime(value: datetime) -> str:
        return value.isoformat().replace("+00:00", "Z")
