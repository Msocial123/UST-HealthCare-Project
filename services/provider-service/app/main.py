"""Provider Service application factory.

Run with: uvicorn app.main:create_app --factory
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import health
from app.api.errors import register_exception_handlers
from app.api.middleware import register_request_logging
from app.api.v1 import providers, specialties
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
        title="Smart Hospital - Provider Service",
        version="0.1.0",
        description=(
            "Development-demo provider directory: provider profiles, specialties and active status. "
            "Verifies Identity-service JWTs locally. Synthetic data only; not a certified clinical system."
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
    for router in (specialties.router, providers.router):
        app.include_router(router, prefix=API_V1_PREFIX)
    return app
