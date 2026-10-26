"""Tests for conversations and chat."""


def test_conversation_lifecycle(auth_client):
    created = auth_client.post("/api/conversations", json={"title": "Trip planning"})
    assert created.status_code == 201
    conv_id = created.json()["id"]

    listed = auth_client.get("/api/conversations")
    assert listed.status_code == 200
    assert any(c["id"] == conv_id for c in listed.json())

    renamed = auth_client.patch(f"/api/conversations/{conv_id}", json={"title": "Karachi trip"})
    assert renamed.status_code == 200
    assert renamed.json()["title"] == "Karachi trip"

    deleted = auth_client.delete(f"/api/conversations/{conv_id}")
    assert deleted.status_code == 204
    assert auth_client.get(f"/api/conversations/{conv_id}").status_code == 404


def test_conversations_require_auth(client):
    assert client.get("/api/conversations").status_code == 401


def test_missing_conversation_returns_404(auth_client):
    assert auth_client.get("/api/conversations/999999").status_code == 404


def test_chat_persists_both_messages(auth_client):
    conv_id = auth_client.post("/api/conversations", json={}).json()["id"]
    response = auth_client.post(f"/api/chat/{conv_id}", json={"content": "Hello there"})
    assert response.status_code == 200
    body = response.json()
    assert body["user_message"]["role"] == "user"
    assert body["assistant_message"]["role"] == "assistant"
    assert body["assistant_message"]["content"]

    detail = auth_client.get(f"/api/conversations/{conv_id}").json()
    assert len(detail["messages"]) == 2


def test_first_message_becomes_the_title(auth_client):
    conv_id = auth_client.post("/api/conversations", json={}).json()["id"]
    auth_client.post(f"/api/chat/{conv_id}", json={"content": "How do I deploy to Vercel?"})
    detail = auth_client.get(f"/api/conversations/{conv_id}").json()
    assert detail["title"].startswith("How do I deploy")


def test_chat_rejects_blank_content(auth_client):
    conv_id = auth_client.post("/api/conversations", json={}).json()["id"]
    assert auth_client.post(f"/api/chat/{conv_id}", json={"content": "   "}).status_code == 422


def test_chat_stream_emits_sse_events(auth_client):
    conv_id = auth_client.post("/api/conversations", json={}).json()["id"]
    with auth_client.stream(
        "POST", f"/api/chat/{conv_id}/stream", json={"content": "Hi", "stream": True}
    ) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        body = "".join(response.iter_text())
    assert '"type": "start"' in body
    assert '"type": "delta"' in body
    assert '"type": "done"' in body


def test_conversation_is_private_to_its_owner(client):
    first = client.post(
        "/api/auth/register",
        json={"email": "owner@example.com", "display_name": "O", "password": "password123"},
    ).json()["access_token"]
    conv_id = client.post("/api/conversations", json={}, headers={"Authorization": f"Bearer {first}"}).json()[
        "id"
    ]

    second = client.post(
        "/api/auth/register",
        json={"email": "intruder@example.com", "display_name": "I", "password": "password123"},
    ).json()["access_token"]
    response = client.get(f"/api/conversations/{conv_id}", headers={"Authorization": f"Bearer {second}"})
    assert response.status_code == 404
