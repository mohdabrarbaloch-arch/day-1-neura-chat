# Setup

## Requirements

- Python 3.11 or newer
- pip
- Docker (optional, for the Postgres stack)

## Local development

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

The app is now on <http://127.0.0.1:8000>. The database file `neurachat.db` is
created automatically on first boot — there is no migration step to run.

### Using a real model

Open `.env` and set:

```
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
```

Restart the server. The sidebar footer will switch from "Local demo engine" to
"OpenAI engine". Any OpenAI-compatible endpoint works — point
`OPENAI_BASE_URL` at Groq, Together, Azure OpenAI, or a local Ollama server.

### Generating a production secret

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Put the result in `JWT_SECRET`. Never commit `.env`.

## Docker

```bash
docker compose up --build
```

This starts two services:

- `db` — PostgreSQL 16, with a healthcheck so the API waits for it
- `api` — the FastAPI app, built from the local `Dockerfile`

The API is on <http://localhost:8000>. Data persists in the `pgdata` volume;
`docker compose down -v` removes it.

## Running the tests

```bash
pytest -q
```

Tests use an isolated SQLite file and the offline engine, so they need no
network access and no API key. The database is created and dropped by the
session fixture.

## Linting and formatting

```bash
ruff check .        # add --fix to auto-fix
black .             # add --check to verify only
```

Both are configured in `pyproject.toml` (line length 110).

## Troubleshooting

**`email-validator is not installed`** — Pydantic needs it for `EmailStr`:

```bash
pip install email-validator
```

**`ModuleNotFoundError: No module named 'app'`** — run commands from the
project root, not from inside `app/`.

**Port already in use** — `uvicorn app.main:app --port 8001`.

**Postgres connection refused** — the API starts before the database is ready.
`docker compose` handles this with a healthcheck; if you run the API outside
Docker, wait a few seconds and retry.
