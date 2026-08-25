"""Safe application logging configuration."""

from __future__ import annotations

import logging
import sys
import time
from collections.abc import Iterable
from typing import TextIO


class SecretRedactionFilter(logging.Filter):
    """Redact configured secret values after log argument interpolation."""

    def __init__(self, secrets: Iterable[str] = ()) -> None:
        super().__init__()
        self._secrets = tuple(secret for secret in secrets if secret)

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        for secret in self._secrets:
            message = message.replace(secret, "[REDACTED]")
        record.msg = message
        record.args = ()
        return True


def configure_logging(
    *,
    level: str = "INFO",
    secrets: Iterable[str] = (),
    stream: TextIO | None = None,
) -> None:
    """Configure one readable root handler with explicit secret redaction."""
    handler = logging.StreamHandler(stream or sys.stderr)
    handler.addFilter(SecretRedactionFilter(secrets))
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%SZ",
        )
    )
    logging.Formatter.converter = time.gmtime

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(level.upper())
