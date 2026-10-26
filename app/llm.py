"""LLM engine.

Two interchangeable backends behind one async generator interface:

* `OpenAIEngine`  - any OpenAI-compatible chat-completions endpoint.
* `LocalEngine`   - a deterministic offline engine so the app is fully usable
                    (and testable) with no API key at all.

`get_engine()` picks one from configuration; nothing else in the codebase
needs to know which is active.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Protocol

import httpx

from app.config import settings


class LLMEngine(Protocol):
    name: str

    def stream(self, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        """Yield response text chunks for a chat history."""
        ...


class LocalEngine:
    """Offline demo engine.

    It is deliberately simple but genuinely useful: it answers common
    greetings, echoes the question back with structure, and streams the reply
    word by word so the UI's streaming path is exercised for real.
    """

    name = "local-demo"

    _GREETINGS = ("hi", "hello", "hey", "salam", "assalam", "aoa")

    def _compose(self, messages: list[dict[str, str]]) -> str:
        last_user = next(
            (m["content"] for m in reversed(messages) if m.get("role") == "user"),
            "",
        )
        lowered = last_user.strip().lower()

        if not last_user:
            return "I'm ready when you are - send me a message and I'll help."

        if lowered in self._GREETINGS or lowered.startswith(("hi ", "hello ", "hey ")):
            return (
                "Hey! I'm NeuraChat running in local demo mode. "
                "Ask me anything and I'll show you the streaming pipeline end to end. "
                "Add an OPENAI_API_KEY to .env to switch to a real model."
            )

        if lowered.endswith("?"):
            return (
                f'Good question: "{last_user}"\n\n'
                "Here's how I'd approach it:\n"
                "1. Break the problem into the smallest testable piece.\n"
                "2. Write down what a correct answer looks like before you build.\n"
                "3. Ship the smallest version, then iterate on real feedback.\n\n"
                "(Local demo mode - connect a model for a full answer.)"
            )

        return (
            f'You said: "{last_user}"\n\n'
            "I'm in local demo mode, so I can't reason about this deeply yet. "
            "Set OPENAI_API_KEY in your .env and I'll answer properly - "
            "the streaming, history and auth layers are all live already."
        )

    async def stream(self, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        text = self._compose(messages)
        for token in text.split(" "):
            yield token + " "
            await asyncio.sleep(0.02)


class OpenAIEngine:
    """Streams from any OpenAI-compatible /chat/completions endpoint."""

    name = "openai"

    def __init__(self) -> None:
        self._url = f"{settings.openai_base_url.rstrip('/')}/chat/completions"
        self._headers = {
            "Authorization": f"Bearer {settings.openai_api_key}",
            "Content-Type": "application/json",
        }

    async def stream(self, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        payload = {
            "model": settings.openai_model,
            "messages": messages,
            "stream": True,
            "temperature": 0.7,
        }
        timeout = httpx.Timeout(settings.llm_timeout_seconds, connect=10.0)
        async with (
            httpx.AsyncClient(timeout=timeout) as client,
            client.stream("POST", self._url, headers=self._headers, json=payload) as response,
        ):
            if response.status_code >= 400:
                body = (await response.aread()).decode("utf-8", "replace")[:300]
                yield f"\n[upstream error {response.status_code}] {body}"
                return
            async for line in response.aiter_lines():
                if not line or not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                except json.JSONDecodeError:
                    continue
                choices = chunk.get("choices") or []
                if not choices:
                    continue
                delta = choices[0].get("delta") or {}
                piece = delta.get("content")
                if piece:
                    yield piece


def get_engine() -> LLMEngine:
    """Return the configured engine (falls back to local when no key is set)."""
    provider = (settings.llm_provider or "auto").lower()
    if provider == "local":
        return LocalEngine()
    if provider == "openai":
        return OpenAIEngine() if settings.has_llm_key else LocalEngine()
    return OpenAIEngine() if settings.has_llm_key else LocalEngine()
