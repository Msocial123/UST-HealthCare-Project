import logging
import re
import time
import uuid

from fastapi import FastAPI, Request, Response

from app.api.errors import internal_error_response

logger = logging.getLogger("app.access")
_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9-]{1,64}$")


def register_request_logging(app: FastAPI) -> None:
    @app.middleware("http")
    async def log_requests(request: Request, call_next) -> Response:
        incoming = request.headers.get("x-request-id", "")
        request_id = incoming if _REQUEST_ID_PATTERN.match(incoming) else str(uuid.uuid4())
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception as exc:
            # Handled here (not by the outer server-error handler) so the 500 keeps the request ID.
            logger.error(
                "unhandled_error",
                extra={"event": "unhandled_error", "request_id": request_id, "exc_type": type(exc).__name__},
            )
            response = internal_error_response()
        # Only method, endpoint name (never the raw path or query), status and timing are logged.
        endpoint = request.scope.get("endpoint")
        route = getattr(endpoint, "__name__", None) or "<unmatched>"
        logger.info(
            "request",
            extra={
                "event": "http_request",
                "request_id": request_id,
                "method": request.method,
                "route": route,
                "status_code": response.status_code,
                "duration_ms": round((time.perf_counter() - start) * 1000, 2),
            },
        )
        response.headers["X-Request-ID"] = request_id
        return response
