# API reference

Base URL: `http://127.0.0.1:8000` in development.

All endpoints except `/api/health`, `/api/auth/register` and `/api/auth/login`
require an `Authorization: Bearer <token>` header.

Errors use FastAPI's standard shape:

```json
{ "detail": "Human-readable message" }
```

| Status | Meaning here |
|---|---|
| 200 | Success |
| 201 | Created (register, new conversation) |
| 204 | Deleted, no body |
| 401 | Missing, invalid or expired token; bad credentials |
| 404 | Not found — **or** owned by another user |
| 409 | Email already registered |
| 422 | Validation failed (bad email, short password, blank content) |
| 429 | Rate limit exceeded — `Retry-After: 60` |
| 500 | Unhandled error (detail hidden unless `DEBUG=true`) |

---

## `GET /api/health`

Liveness probe. No auth.

```json
{
  "status": "ok",
  "app": "NeuraChat",
  "version": "1.0.0",
  "environment": "development",
  "llm_provider": "local-demo",
  "database": "sqlite"
}
```

## `POST /api/auth/register`

```json
{ "email": "you@example.com", "display_name": "Ayesha", "password": "at-least-8-chars" }
```

`201` →

```json
{
  "access_token": "eyJhbGciOi...",
  "token_type": "bearer",
  "expires_in": 604800,
  "user": { "id": 1, "email": "you@example.com", "display_name": "Ayesha", "created_at": "..." }
}
```

`409` if the email is taken. `422` if the password is under 8 characters or the
email is malformed.

## `POST /api/auth/login`

```json
{ "email": "you@example.com", "password": "at-least-8-chars" }
```

`200` with the same body as register. `401` with
`"Incorrect email or password."` for both a wrong password and an unknown
email — deliberately identical so the endpoint can't enumerate accounts.

## `GET /api/auth/me`

`200` → the `user` object. `401` without a valid token.

---

## `GET /api/conversations`

`200` → array of conversations, most recently updated first.

```json
[{ "id": 1, "title": "Karachi trip", "model": "default", "created_at": "...", "updated_at": "..." }]
```

## `POST /api/conversations`

```json
{ "title": "New chat", "model": "default" }
```

Both fields optional. `201` → the created conversation.

## `GET /api/conversations/{id}`

`200` → the conversation plus its full message history:

```json
{
  "id": 1, "title": "Karachi trip", "model": "default",
  "created_at": "...", "updated_at": "...",
  "messages": [
    { "id": 1, "role": "user", "content": "Hello", "created_at": "..." },
    { "id": 2, "role": "assistant", "content": "Hey! ...", "created_at": "..." }
  ]
}
```

`404` if it doesn't exist **or belongs to another user**.

## `PATCH /api/conversations/{id}`

```json
{ "title": "Renamed" }
```

`200` → the updated conversation.

## `DELETE /api/conversations/{id}`

`204`, no body. Messages are deleted with it (cascade).

---

## `POST /api/chat/{id}`

Non-streaming. Waits for the full reply.

```json
{ "content": "How do I start?", "stream": false }
```

`200` →

```json
{
  "conversation_id": 1,
  "user_message": { "id": 3, "role": "user", "content": "How do I start?", "created_at": "..." },
  "assistant_message": { "id": 4, "role": "assistant", "content": "Good question...", "created_at": "..." }
}
```

## `POST /api/chat/{id}/stream`

Streams the reply as Server-Sent Events. `Content-Type: text/event-stream`.

```json
{ "content": "How do I start?", "stream": true }
```

Event sequence:

```
data: {"type": "start", "user_message_id": 3}

data: {"type": "delta", "content": "Good "}

data: {"type": "delta", "content": "question..."}

data: {"type": "done", "assistant_message_id": 4}
```

On an engine failure mid-stream:

```
data: {"type": "error", "message": "upstream error 401 ..."}
```

The assistant message is persisted when the stream completes, on a fresh
database session — the request-scoped session is already closed by then.

### Reading the stream from JavaScript

```js
const res = await fetch(`/api/chat/${id}/stream`, {
  method: "POST",
  headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
  body: JSON.stringify({ content: "Hello", stream: true }),
});
const reader = res.body.getReader();
const decoder = new TextDecoder();
let buffer = "";
while (true) {
  const { value, done } = await reader.read();
  if (done) break;
  buffer += decoder.decode(value, { stream: true });
  const parts = buffer.split("\n\n");
  buffer = parts.pop();
  for (const part of parts) {
    const line = part.split("\n").find((l) => l.startsWith("data:"));
    if (!line) continue;
    const evt = JSON.parse(line.slice(5).trim());
    if (evt.type === "delta") process.stdout.write(evt.content);
  }
}
```

### Reading the stream from the shell

```bash
curl -N -X POST http://127.0.0.1:8000/api/chat/1/stream \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"content":"Hello","stream":true}'
```
