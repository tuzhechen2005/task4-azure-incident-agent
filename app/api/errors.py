"""Safe HTTP error types and response handlers."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse

from app.models.schemas import ErrorDetail, ErrorResponse

LOGGER = logging.getLogger(__name__)


class ApplicationError(RuntimeError):
    """A controlled error whose safe fields may cross the HTTP boundary."""

    def __init__(
        self,
        *,
        code: str,
        message: str,
        status_code: int,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details


def _request_id(request: Request) -> str:
    return str(getattr(request.state, "request_id", "unknown"))


async def application_error_handler(
    request: Request, error: ApplicationError
) -> JSONResponse:
    payload = ErrorResponse(
        error=ErrorDetail(
            code=error.code,
            message=error.message,
            details=error.details,
            request_id=_request_id(request),
        )
    )
    return JSONResponse(
        status_code=error.status_code, content=payload.model_dump(mode="json")
    )


async def unexpected_error_handler(request: Request, error: Exception) -> JSONResponse:
    LOGGER.error(
        "Unhandled API error request_id=%s type=%s",
        _request_id(request),
        type(error).__name__,
    )
    payload = ErrorResponse(
        error=ErrorDetail(
            code="INTERNAL_ERROR",
            message="An unexpected internal error occurred.",
            request_id=_request_id(request),
        )
    )
    return JSONResponse(status_code=500, content=payload.model_dump(mode="json"))
