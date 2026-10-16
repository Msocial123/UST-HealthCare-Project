from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


def build_engine(database_url: str) -> Engine:
    if database_url.startswith("sqlite"):
        # Used by the isolated test suite; a single shared connection keeps in-memory databases alive.
        return create_engine(database_url, connect_args={"check_same_thread": False}, poolclass=StaticPool)
    return create_engine(database_url, pool_pre_ping=True)


def build_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
