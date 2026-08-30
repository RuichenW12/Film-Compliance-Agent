"""Application errors mapped to the API error envelope (contract section 1)."""

from __future__ import annotations

from schemas.enums import ErrorCode

STATUS_BY_CODE: dict[ErrorCode, int] = {
    ErrorCode.VALIDATION_ERROR: 422,
    ErrorCode.NOT_FOUND: 404,
    ErrorCode.FORBIDDEN: 403,
    ErrorCode.CONFLICT: 409,
    ErrorCode.GATE_BLOCKED: 409,
    ErrorCode.STATE_INVALID: 409,
    ErrorCode.UPSTREAM_LLM_ERROR: 502,
    ErrorCode.RATE_LIMITED: 429,
    ErrorCode.UNSUPPORTED_SCRIPT_TYPE: 422,
    ErrorCode.UNREADABLE_SCRIPT: 422,
    ErrorCode.SCRIPT_TOO_LARGE: 413,
    ErrorCode.ARTIFACT_UNAVAILABLE: 409,
    ErrorCode.ARTIFACT_GENERATION_FAILED: 503,
}


class AppError(Exception):
    """Every non-2xx response body is built from one of these."""

    code = ErrorCode.CONFLICT

    def __init__(self, message: str, details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}

    @property
    def status_code(self) -> int:
        return STATUS_BY_CODE[self.code]

    def envelope(self) -> dict:
        return {
            "error": {
                "code": self.code.value,
                "message": self.message,
                "details": self.details,
            }
        }


class NotFoundError(AppError):
    code = ErrorCode.NOT_FOUND


class ForbiddenError(AppError):
    code = ErrorCode.FORBIDDEN


class ValidationFailedError(AppError):
    code = ErrorCode.VALIDATION_ERROR


class ConflictError(AppError):
    code = ErrorCode.CONFLICT


class StateInvalidError(AppError):
    code = ErrorCode.STATE_INVALID


class GateBlockedError(AppError):
    code = ErrorCode.GATE_BLOCKED


class UpstreamLLMError(AppError):
    code = ErrorCode.UPSTREAM_LLM_ERROR


class RateLimitedError(AppError):
    code = ErrorCode.RATE_LIMITED


class UnsupportedScriptTypeError(AppError):
    code = ErrorCode.UNSUPPORTED_SCRIPT_TYPE


class UnreadableScriptError(AppError):
    code = ErrorCode.UNREADABLE_SCRIPT


class ScriptTooLargeError(AppError):
    code = ErrorCode.SCRIPT_TOO_LARGE


class ArtifactUnavailableError(AppError):
    code = ErrorCode.ARTIFACT_UNAVAILABLE


class ArtifactGenerationFailedError(AppError):
    code = ErrorCode.ARTIFACT_GENERATION_FAILED
