"""Appointment Service application factory.

Run with: uvicorn app.main:create_app --factory
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import health
from app.api.errors import register_exception_handlers
from app.api.middleware import register_request_logging
from app.api.v1 import appointments
from app.clients.scheduling_client import HttpSchedulingClient, SchedulingClient
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.core.time import utcnow
from app.core.tokens import TokenVerifier
from app.db.session import build_engine, build_session_factory

API_V1_PREFIX = "/api/v1"


def create_app(
    settings: Settings | None = None, *, scheduling_client: SchedulingClient | None = None
) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)
    engine = build_engine(settings.database_url)
    owned_client = None
    if settings.scheduling_advice_enabled and scheduling_client is None:
        # SCHEDULING_SERVICE_URL is required by Settings validation whenever advice is enabled.
        owned_client = HttpSchedulingClient(
            str(settings.scheduling_service_url), settings.scheduling_timeout_seconds
        )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        if owned_client is not None:
            owned_client.close()
        engine.dispose()

    app = FastAPI(
        title="Smart Hospital - Appointment Service",
        version="0.1.0",
        description=(
            "Development-demo appointment booking lifecycle: book, reschedule, cancel, check-in, complete "
            "and no-show. Double-booking is prevented by a PostgreSQL exclusion constraint; domain events "
            "are written to a transactional outbox. Book/reschedule/cancel are behind the "
            "APPOINTMENTS_ENABLED feature flag (503 `feature_disabled` when off). Verifies Identity-service "
            "JWTs locally. Synthetic data only; not a certified clinical system."
        ),
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = build_session_factory(engine)
    app.state.token_verifier = TokenVerifier(settings)
    app.state.scheduling_client = (
        (scheduling_client or owned_client) if settings.scheduling_advice_enabled else None
    )
    app.state.clock = utcnow

    register_request_logging(app)
    register_exception_handlers(app)
    app.include_router(health.router)
    app.include_router(appointments.router, prefix=API_V1_PREFIX)
    return app
