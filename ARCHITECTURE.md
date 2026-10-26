# Architecture — NeuraChat

## What this is

NeuraChat is a conversational AI assistant backend with a single-page chat UI.
It does four things well: authenticates users, stores conversations, streams
model output token by token, and keeps every conversation private to its owner.

## System diagram

```
                        ┌──────────────────────────────────────────┐
                        │            Browser (SPA)                 │
                        │  app/static/index.html                   │
                        │  · auth modal (register / login)         │
                        │  · conversation sidebar                  │
                        │  · SSE reader for streaming replies      │
                        └───────────────┬──────────────────────────┘
                                        │  fetch() + Bearer JWT
                                        ▼
┌───────────────────────────────────────────────────────────────────────┐
│                        FastAPI application                            │
│                        app/main.py                                    │
│                                                                       │
│  middleware:  CORS  ·  security headers  ·  global error handler      │
│                                                                       │
│  ┌──────────────┐  ┌────────────────────┐  ┌──────────────────────┐   │
│  │ /api/auth    │  │ /api/conversations │  │ /api/chat            │   │
│  │ register     │  │ list / create      │  │ POST /{id}           │   │
│  │ login        │  │ get / patch        │  │ POST /{id}/stream    │   │
│  │ me           │  │ delete             │  │   (SSE)              │   │
│  └──────┬───────┘  └─────────┬──────────┘  └──────────┬───────────┘   │
│         │                    │                        │               │
│         │  deps.py: get_current_user (JWT) · rate_limit (per-IP)      │
│         │                    │                        │               │
│         ▼                    ▼                        ▼               │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │  SQLAlchemy ORM  (app/models.py)                                │  │
│  │  User 1───* Conversation 1───* Message                          │  │
│  └────────────────────────────┬────────────────────────────────────┘  │
│                               │                                       │
│  ┌────────────────────────────▼────────────────────────────────────┐  │
│  │  LLM engine (app/llm.py) — one async-generator interface        │  │
│  │  · OpenAIEngine  → any OpenAI-compatible /chat/completions      │  │
│  │  · LocalEngine   → deterministic offline demo engine            │  │
│  └─────────────────────────────────────────────────────────────────┘  │
└───────────────────────────────┬───────────────────────────────────────┘
                                │
                                ▼
                 ┌──────────────────────────────┐
                 │  SQLite (default, zero-conf) │
                 │  PostgreSQL (docker-compose) │
                 └──────────────────────────────┘
```

## Tech stack

| Layer | Choice | Why |
|---|---|---|
| Web framework | FastAPI 0.115 | Async-native, typed, auto OpenAPI docs |
| ASGI server | Uvicorn | Standard, production-ready |
| ORM | SQLAlchemy 2.0 (typed `Mapped[]`) | Works with SQLite and PostgreSQL unchanged |
| Validation | Pydantic v2 | Request/response contracts, env settings |
| Auth | PyJWT + bcrypt | Small surface, no passlib indirection |
| HTTP client | httpx | Async streaming from the model provider |
| Frontend | Vanilla JS + CSS | No build step, no framework churn, fast |
| Tests | pytest + FastAPI TestClient | 33 tests, no network required |
| Lint/format | ruff + black | Fast, deterministic |
| Containers | Docker + docker-compose | One command to a full stack |

## Data flow — a streamed message

1. The SPA sends `POST /api/chat/{id}/stream` with a Bearer token.
2. `get_current_user` decodes the JWT and loads the `User` row.
3. `rate_limit` checks the caller's per-minute budget.
4. The user's message is persisted immediately, so it survives a dropped
   connection. The first message also becomes the conversation title.
5. The last 20 messages are replayed as context to the engine.
6. The engine yields text chunks; each is wrapped as an SSE `delta` event.
7. On completion the assistant message is written **on a fresh session** —
   the request-scoped session is already closed by the time a streaming body
   finishes, which is the classic FastAPI streaming bug.
8. The client receives `start` → `delta`* → `done`.

## Security model

- Passwords hashed with **bcrypt, cost 12**; inputs truncated at bcrypt's
  72-byte limit rather than rejected.
- **JWT** (HS256) with `sub`, `iat`, `exp`. Invalid or expired tokens → 401.
- Login returns the **same message** for unknown email and wrong password, so
  the endpoint can't be used to enumerate accounts.
- Every conversation query is scoped by `user_id`; another user's conversation
  returns **404, not 403** — it doesn't confirm the row exists.
- Baseline headers on every response: `X-Content-Type-Options`,
  `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`.
- Stack traces are never returned when `DEBUG=false`.
- **No secret is hardcoded.** Everything comes from the environment.

## Scaling notes

| Concern | Now | Next step |
|---|---|---|
| Rate limiting | In-process sliding window | Redis-backed limiter for multi-instance |
| Sessions | Stateless JWT | Add refresh tokens + revocation list |
| Database | SQLite / single Postgres | Read replicas, connection pooling (PgBouncer) |
| Streaming | Direct SSE from the app | Dedicated worker + message queue for long jobs |
| Context window | Last 20 messages | Summarise older turns, or vector retrieval |
| Caching | None | Cache model responses by prompt hash |
| Observability | Uvicorn logs | Structured JSON logs + OpenTelemetry traces |

## Deliberate trade-offs

- **No passlib.** bcrypt is used directly — one less dependency and the cost
  factor is explicit.
- **Vanilla frontend.** A React build would add a toolchain for a UI that is
  one screen. The SSE reader is ~40 lines of plain JS.
- **Local demo engine.** The app is fully usable and testable with no API key,
  which also means CI never needs a secret.
