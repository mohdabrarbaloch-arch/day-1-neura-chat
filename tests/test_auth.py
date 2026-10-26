"""Tests for the auth endpoints."""


def test_health_endpoint(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["llm_provider"] == "local-demo"


def test_register_returns_token_and_user(client):
    response = client.post(
        "/api/auth/register",
        json={"email": "new@example.com", "display_name": "New", "password": "password123"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["email"] == "new@example.com"
    assert "password" not in body["user"]


def test_register_rejects_duplicate_email(client):
    payload = {"email": "dupe@example.com", "display_name": "D", "password": "password123"}
    assert client.post("/api/auth/register", json=payload).status_code == 201
    assert client.post("/api/auth/register", json=payload).status_code == 409


def test_register_rejects_short_password(client):
    response = client.post(
        "/api/auth/register",
        json={"email": "short@example.com", "display_name": "S", "password": "abc"},
    )
    assert response.status_code == 422


def test_register_rejects_invalid_email(client):
    response = client.post(
        "/api/auth/register",
        json={"email": "not-an-email", "display_name": "X", "password": "password123"},
    )
    assert response.status_code == 422


def test_login_succeeds_with_correct_credentials(client):
    client.post(
        "/api/auth/register",
        json={"email": "login@example.com", "display_name": "L", "password": "password123"},
    )
    response = client.post("/api/auth/login", json={"email": "login@example.com", "password": "password123"})
    assert response.status_code == 200
    assert response.json()["access_token"]


def test_login_fails_with_wrong_password(client):
    client.post(
        "/api/auth/register",
        json={"email": "wrong@example.com", "display_name": "W", "password": "password123"},
    )
    response = client.post(
        "/api/auth/login", json={"email": "wrong@example.com", "password": "nope-nope-nope"}
    )
    assert response.status_code == 401


def test_login_does_not_reveal_whether_email_exists(client):
    missing = client.post("/api/auth/login", json={"email": "ghost@example.com", "password": "password123"})
    assert missing.status_code == 401
    assert missing.json()["detail"] == "Incorrect email or password."


def test_me_requires_authentication(client):
    assert client.get("/api/auth/me").status_code == 401


def test_me_returns_current_user(auth_client):
    response = auth_client.get("/api/auth/me")
    assert response.status_code == 200
    assert response.json()["email"] == "tester@example.com"


def test_me_rejects_garbage_token(client):
    response = client.get("/api/auth/me", headers={"Authorization": "Bearer not.a.jwt"})
    assert response.status_code == 401
