"""Typed pipeline errors. Each one knows its HTTP status and its error body."""
from typing import Any, Dict, Optional


class PipelineError(Exception):
    http_status = 500
    status = "HALTED_INTERNAL_ERROR"
    error_type = "INTERNAL_FAILURE"

    def __init__(self, message: str, details: Optional[Any] = None):
        super().__init__(message)
        self.message = message
        self.details = details

    def to_response(self) -> Dict[str, Any]:
        error: Dict[str, Any] = {"type": self.error_type, "message": self.message}
        if self.details:
            error["details"] = self.details
        return {"status": self.status, "code": self.http_status, "error": error}


# --- the caller sent something we refuse -------------------------------------
class SecurityViolationError(PipelineError):
    """Restricted field / tenant boundary. The caller is not allowed to ask for this."""
    http_status = 403
    status = "HALTED_SECURITY_VIOLATION"
    error_type = "SECURITY_RESTRICTION"


class MaliciousInputError(SecurityViolationError):
    """SQL-style or prompt-injection input. Malformed/hostile request -> 400."""
    http_status = 400
    error_type = "MALICIOUS_INPUT"


# --- the request is well-formed but cannot be turned into a filter -----------
class InvalidInputError(PipelineError):
    http_status = 422
    status = "HALTED_VALIDATION_ERROR"
    error_type = "INVALID_INPUT"


class ConflictingConditionsError(InvalidInputError):
    error_type = "CONFLICTING_CONDITIONS"


class NoSupportedConditionsError(InvalidInputError):
    error_type = "NO_SUPPORTED_CONDITIONS"


class UnsupportedConditionError(InvalidInputError):
    """Only raised when the pipeline runs in strict mode."""
    error_type = "UNSUPPORTED_CONDITIONS"


# --- the LLM dependency failed ----------------------------------------------
class LLMUnavailableError(PipelineError):
    http_status = 503
    status = "HALTED_UPSTREAM_UNAVAILABLE"
    error_type = "LLM_UNAVAILABLE"


class LLMTimeoutError(LLMUnavailableError):
    http_status = 504
    error_type = "LLM_TIMEOUT"


class LLMOutputError(PipelineError):
    http_status = 502
    status = "HALTED_UPSTREAM_ERROR"
    error_type = "LLM_BAD_OUTPUT"
