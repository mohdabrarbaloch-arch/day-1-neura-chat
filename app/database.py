"""Database engine, session factory and declarative base.

SQLite is the zero-config default so the project runs anywhere; PostgreSQL is
used automatically when `DATABASE_URL` points at it (docker-compose does this).
"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


def _engine_kwargs(url: str) -> dict:
    if url.startswith("sqlite"):
        # SQLite connections are used from FastAPI's threadpool, so the
        # same-thread check has to be relaxed.
        return {"connect_args": {"check_same_thread": False}}
    return {"pool_pre_ping": True, "pool_size": 5, "max_overflow": 10, "pool_recycle": 1800}


engine = create_engine(settings.database_url, **_engine_kwargs(settings.database_url))

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a scoped session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create tables if they do not exist yet."""
    from app import models  # noqa: F401  (import registers the mappers)

    Base.metadata.create_all(bind=engine)
