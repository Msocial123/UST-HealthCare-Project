import logging
import re
import time
import uuid

from fastapi import FastAPI, Request, Response

logger = logging.getLogger("app.access")
_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9-]{1,64}$")


def register_request_logging(app: FastAPI) -> None:
    @app.middleware("http")
    async def log_requests(request: Request, call_next) -> Response:
        incoming = request.headers.get("x-request-id", "")
        request_id = incoming if _REQUEST_ID_PATTERN.match(incoming) else str(uuid.uuid4())
        start = time.perf_counter()
        response = await call_next(request)
        # Only method, path (no query string), status and timing are logged; never headers or bodies.
        logger.info(
            "request",
            extra={
                "event": "http_request",
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": round((time.perf_counter() - start) * 1000, 2),
            },
        )
        response.headers["X-Request-ID"] = request_id
        return response
