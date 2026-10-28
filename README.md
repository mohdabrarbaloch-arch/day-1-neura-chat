# NeuraChat

**A conversational AI assistant backend with a single-page chat UI.** Authenticates users, stores conversations, streams model output token by token, and keeps every conversation private to its owner.

---

## What it does

- **Accounts** — register/login with bcrypt-hashed passwords and JWT sessions
- **Conversations** — create, list, rename and delete; each one scoped to its owner
- **Streaming replies** — answers arrive token by token over Server-Sent Events, not in one lump
- **Two engines behind one interface** — an OpenAI-compatible engine for real models, and a deterministic offline engine so the app runs with no API key at all

The first message in a conversation becomes its title, so the sidebar names itself.

## Quick start

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open <http://localhost:8000>. With no API key configured the offline engine answers, so the app is fully usable on first run — nothing to sign up for, nothing to configure.

To use a real model:

```bash
cp .env.example .env
# then set OPENAI_API_KEY in .env
```

## API

Base path `/api`. Full reference in [docs/api.md](docs/api.md).

| Route | Purpose |
|---|---|
| `POST /api/auth/register` | Create an account, returns a token |
| `POST /api/auth/login` | Exchange credentials for a token |
| `GET /api/auth/me` | Current account |
| `GET /api/conversations` | List your conversations |
| `POST /api/conversations` | Create one |
| `GET /api/conversations/{id}` | Read one |
| `PATCH /api/conversations/{id}` | Rename |
| `DELETE /api/conversations/{id}` | Delete |
| `POST /api/chat/{id}/stream` | **SSE** — send a message, stream the reply |

Streaming shape:

```
event: start
data: {"conversation_id": "..."}

event: delta
data: {"text": "Hello"}

event: done
data: {"message_id": "...", "latency_ms": 812.4}
```

## Design decisions

**No passlib.** bcrypt is called directly — one less dependency, and the cost factor (12) is visible in the code rather than buried in a hashing-context factory.

**Ownership failures return 404, not 403.** A 403 on someone else's conversation confirms the row exists, which turns an ID guess into a directory of other users' chats. 404 keeps it invisible.

**Login is not an account oracle.** An unknown email and a wrong password produce the identical error message, so the endpoint can't be used to discover who has an account.

**The assistant message is written on a fresh session.** The request-scoped session is already closed by the time a streaming response body finishes — the classic FastAPI streaming bug. `chat.py` opens its own session for the write.

**The offline engine is not a stub.** It exists so the app is testable, demoable and CI-friendly without a secret. It produces deterministic text, which is also what makes the streaming tests reliable.

## Verification

- **33 tests passing** — auth, conversations, LLM engines, security. No network required.
- **Ruff + Black clean.**
- Docker Compose brings up SQLite (default) or Postgres with one command.

## Stack

FastAPI 0.115 · Uvicorn · SQLAlchemy 2.0 · Pydantic v2 · PyJWT + bcrypt · httpx · vanilla JS frontend (no build step) · pytest

See [ARCHITECTURE.md](ARCHITECTURE.md) for the system diagram, data flow, security model and scaling notes.

## Notes

Images and PDFs are out of scope here — this project is text-only chat. The multimodal companion project is [day-2-aurora-workspace](https://github.com/mohdabrarbaloch-arch/day-2-aurora-workspace).

## Deployment

Live at **<https://day-1-neura-chat.vercel.app>**.

### The bug that made it look alive when it wasn't

For a while that URL served a perfect signup form and then answered every submission with `Request failed (500)`. The page was fine. The API was dead.

The cause was in `vercel.json`. It used the legacy `builds` block:

```json
{ "src": "api/index.py", "use": "@vercel/python",
  "config": { "includeFiles": ["app/**"] } }
```

`includeFiles` in that block resolves **relative to the function's own directory** — so `app/**` was looked for at `api/app/**`, which does not exist. The `app` package was never bundled. `api/index.py` then did `from app.main import app` and died with `ModuleNotFoundError: No module named 'app'` on every cold start. Meanwhile `app/static/**` was built separately as static output, so `/` kept serving a cached HTML page. Healthy-looking site, dead API.

The fix is the modern config, where `includeFiles` resolves from the project root:

```json
{
  "functions": { "api/index.py": { "includeFiles": "app/**" } },
  "rewrites": [{ "source": "/(.*)", "destination": "/api/index.py" }]
}
```

Two supporting changes in `app/main.py` so this class of failure can never hide again:

- the static mount is guarded by a real directory check, and `/` returns an explicit `503` with a hint instead of silently falling through
- unknown paths return **JSON 404**, not the SPA shell — so a broken route is visible from `curl` instead of looking like a working page

### Deploying it yourself

```bash
npm i -g vercel
vercel --prod
```

Set `JWT_SECRET` and, if you want real model output, `OPENAI_API_KEY` in the Vercel project's environment variables. Without a key the offline engine answers and everything still works.

**One caveat worth knowing:** the SQLite fallback lives at `/tmp/neurachat.db` on Vercel, and `/tmp` does not survive a cold start. Accounts and conversations created on the live demo can vanish when the function recycles. That is fine for a demo and is exactly why `DATABASE_URL` exists — point it at Postgres and the data sticks.
