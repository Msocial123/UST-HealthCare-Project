"""Patient Service application factory.

Run with: uvicorn app.main:create_app --factory
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import health
from app.api.errors import register_exception_handlers
from app.api.middleware import register_request_logging
from app.api.v1 import patients
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.core.tokens import TokenVerifier
from app.db.session import build_engine, build_session_factory

API_V1_PREFIX = "/api/v1"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)
    engine = build_engine(settings.database_url)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        engine.dispose()

    app = FastAPI(
        title="Smart Hospital - Patient Service",
        version="0.1.0",
        description=(
            "Development-demo patient registration, demographics and lookup. Authorizes callers by verifying "
            "identity-service access tokens locally. Synthetic data only; not a certified clinical system."
        ),
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = build_session_factory(engine)
    app.state.token_verifier = TokenVerifier(settings)

    register_request_logging(app)
    register_exception_handlers(app)
    app.include_router(health.router)
    app.include_router(patients.router, prefix=API_V1_PREFIX)
    return app
