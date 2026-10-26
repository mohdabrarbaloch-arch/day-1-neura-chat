"""FastAPI application entrypoint.

Wires configuration, database, security middleware, routers and the static UI.
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.config import settings
from app.database import init_db
from app.llm import get_engine
from app.routers import auth, chat, conversations
from app.schemas import HealthOut

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Create tables on boot."""
    init_db()
    yield


app = FastAPI(
    title=settings.app_name,
    version=__version__,
    description=(
        "A conversational AI assistant API: JWT auth, conversation history, "
        "and token-by-token streaming responses."
    ),
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    """Attach baseline security headers to every response."""
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=()")
    return response


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Never leak a stack trace to the client in production."""
    detail = str(exc) if settings.debug else "Internal server error."
    return JSONResponse(status_code=500, content={"detail": detail})


@app.get("/api/health", response_model=HealthOut, tags=["meta"])
def health() -> HealthOut:
    """Liveness probe used by Docker, Vercel and uptime checks."""
    return HealthOut(
        status="ok",
        app=settings.app_name,
        version=__version__,
        environment=settings.environment,
        llm_provider=get_engine().name,
        database=settings.database_url.split("://", 1)[0],
    )


app.include_router(auth.router)
app.include_router(conversations.router)
app.include_router(chat.router)

# --- Static UI -------------------------------------------------------------
if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")
