"""Database engine, session factory and declarative base.

SQLite is the zero-config default so the project runs anywhere; PostgreSQL is
used automatically when `DATABASE_URL` points at it (docker-compose does this).
"""

import os
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


def _resolve_url(url: str) -> str:
    """Point the SQLite fallback at a writable path on serverless hosts.

    Vercel's function bundle (/var/task) is read-only, so the default
    ``sqlite:///./neurachat.db`` cannot create a file there and every request
    dies with ``OperationalError: unable to open database file``. /tmp is the
    one writable location on a Lambda; data does not survive a cold start, which
    is fine for a demo and is why PostgreSQL is the documented production path.
    """
    if url.startswith("sqlite") and os.environ.get("VERCEL"):
        return "sqlite:////tmp/neurachat.db"
    return url


DATABASE_URL = _resolve_url(settings.database_url)
engine = create_engine(DATABASE_URL, **_engine_kwargs(DATABASE_URL))

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
