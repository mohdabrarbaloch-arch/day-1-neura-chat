"""Shared pytest fixtures: an isolated in-memory database and a test client."""

import os
import sys
from pathlib import Path

import pytest

# Make the project importable when pytest is run from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Configure the app for tests BEFORE importing it.
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_neurachat.db")
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production-0123456789abcdef")
os.environ.setdefault("LLM_PROVIDER", "local")
os.environ.setdefault("RATE_LIMIT_PER_MINUTE", "10000")

from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _clean_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    db_file = Path("test_neurachat.db")
    if db_file.exists():
        db_file.unlink()


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def auth_client(client):
    """A client with a registered user and the Authorization header set."""
    payload = {
        "email": "tester@example.com",
        "display_name": "Tester",
        "password": "supersecret123",
    }
    response = client.post("/api/auth/register", json=payload)
    if response.status_code == 409:
        response = client.post(
            "/api/auth/login",
            json={"email": payload["email"], "password": payload["password"]},
        )
    token = response.json()["access_token"]
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client
