"""Stable HTTP error envelope for the policy administration API."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class PolicyApiError(RuntimeError):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}


async def policy_api_error_handler(
    request: Request,
    exc: PolicyApiError,
) -> JSONResponse:
    _ = request
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
            }
        },
    )


def install_policy_error_handler(app: FastAPI) -> None:
    app.add_exception_handler(PolicyApiError, policy_api_error_handler)
