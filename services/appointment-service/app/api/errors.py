import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.errors import AppError

logger = logging.getLogger(__name__)

_HTTP_CODES = {
    401: "not_authenticated",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    503: "service_unavailable",
}

# Pydantic error types whose messages are built only from schema constraints, never from the
# submitted value. Every other type (value_error, email/UUID/JSON parsing, ...) may embed parts
# of the input, so its message is replaced with a generic one.
_SAFE_MESSAGE_TYPES = frozenset(
    {
        "missing",
        "extra_forbidden",
        "string_type",
        "string_too_short",
        "string_too_long",
        "string_pattern_mismatch",
        "int_type",
        "int_parsing",
        "bool_type",
        "bool_parsing",
        "greater_than",
        "greater_than_equal",
        "less_than",
        "less_than_equal",
        "enum",
        "literal_error",
        "dict_type",
        "model_type",
        "model_attributes_type",
        "list_type",
        "uuid_type",
        "uuid_parsing",
        "timezone_aware",
        "invalid_interval",
    }
)
_GENERIC_VALIDATION_MESSAGE = "Invalid value"


def _validation_detail(err: dict[str, Any]) -> dict[str, Any]:
    error_type = str(err.get("type", ""))
    message = err.get("msg", "") if error_type in _SAFE_MESSAGE_TYPES else _GENERIC_VALIDATION_MESSAGE
    return {"loc": list(err.get("loc", ())), "msg": message, "type": error_type}


def internal_error_response(headers: dict[str, str] | None = None) -> JSONResponse:
    return _error(500, "internal_error", "Internal server error", headers=headers)


def _error(status_code: int, code: str, message: str, details: Any = None, headers=None) -> JSONResponse:
    body: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        body["details"] = details
    return JSONResponse(status_code=status_code, content={"error": body}, headers=headers)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return _error(exc.status_code, exc.code, exc.message, exc.details, exc.headers)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        # Never echo submitted values back (they may contain contact details).
        details = [_validation_detail(err) for err in exc.errors()]
        return _error(422, "validation_error", "Request validation failed", details)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _HTTP_CODES.get(exc.status_code, "http_error")
        message = exc.detail if isinstance(exc.detail, str) else "Request failed"
        return _error(exc.status_code, code, message, headers=getattr(exc, "headers", None))

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        logger.error("unhandled_error", extra={"event": "unhandled_error", "exc_type": type(exc).__name__})
        return internal_error_response()
