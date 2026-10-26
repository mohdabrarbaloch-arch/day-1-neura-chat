"""Vercel serverless entrypoint.

Vercel's Python runtime looks for an ASGI callable named `app` in this module.
The real application lives in `app/main.py`; `vercel.json` bundles the whole
`app/` package into this function via `includeFiles`, so the import below
resolves at runtime.
"""

from app.main import app  # noqa: F401

__all__ = ["app"]
