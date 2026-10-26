# Usage

## The 60-second tour

1. Start the server (`uvicorn app.main:app --reload`) and open
   <http://127.0.0.1:8000>.
2. Click **Create an account**, enter a name, email and a password of at least
   8 characters. You're signed in immediately — no email confirmation.
3. Type a message and press **Enter**. The reply streams in word by word.
4. Click **＋ New chat** for a fresh conversation. Everything you've said is in
   the sidebar, newest first.
5. Hover a conversation and click **✕** to delete it.

## What the sidebar tells you

The footer shows which engine is answering:

- **Local demo engine** — no API key configured. Replies are canned but the
  whole pipeline (auth, storage, streaming) is real.
- **OpenAI engine** — a key is set and replies come from the model.

## Keyboard shortcuts

| Key | Action |
|---|---|
| `Enter` | Send the message |
| `Shift` + `Enter` | New line without sending |

The textarea grows as you type, up to about 8 lines.

## Using the API directly

```bash
# 1. Register and capture the token
TOKEN=$(curl -s -X POST http://127.0.0.1:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"me@example.com","display_name":"Me","password":"password123"}' \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

# 2. Start a conversation
CID=$(curl -s -X POST http://127.0.0.1:8000/api/conversations \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{}' \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['id'])")

# 3. Ask something (full reply)
curl -s -X POST "http://127.0.0.1:8000/api/chat/$CID" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"content":"Hello there"}'

# 4. Or stream it
curl -N -X POST "http://127.0.0.1:8000/api/chat/$CID/stream" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"content":"How do I start?","stream":true}'
```

## Swapping in a different model provider

`app/llm.py` talks to any OpenAI-compatible `/chat/completions` endpoint. To use
Groq, for example:

```
OPENAI_API_KEY=gsk_...
OPENAI_BASE_URL=https://api.groq.com/openai/v1
OPENAI_MODEL=llama-3.3-70b-versatile
```

For a local Ollama server:

```
OPENAI_API_KEY=ollama
OPENAI_BASE_URL=http://localhost:11434/v1
OPENAI_MODEL=llama3.2
```

No code changes — the engine is selected from configuration.

## Adding your own engine

Implement the two-line protocol in `app/llm.py`:

```python
class MyEngine:
    name = "my-engine"

    async def stream(self, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        yield "hello "
        yield "world"
```

Then return it from `get_engine()`. Nothing else in the codebase needs to know.

## Notes on behaviour

- The **first user message becomes the conversation title**, truncated at 60
  characters. Rename it any time with `PATCH /api/conversations/{id}`.
- Only the **last 20 messages** are sent as context. Older turns stay in the
  database but aren't replayed to the model.
- A message is saved **before** the model is called, so a dropped connection
  never loses what you typed.
- Rate limiting is **60 requests per minute per IP** by default
  (`RATE_LIMIT_PER_MINUTE`). Exceeding it returns `429` with `Retry-After: 60`.
