"""Tests for the LLM engines."""

import pytest

from app.llm import LocalEngine, get_engine


@pytest.mark.asyncio
async def test_local_engine_streams_multiple_chunks():
    engine = LocalEngine()
    chunks = [c async for c in engine.stream([{"role": "user", "content": "Hello"}])]
    assert len(chunks) > 1
    assert "".join(chunks).strip()


@pytest.mark.asyncio
async def test_local_engine_handles_greeting():
    engine = LocalEngine()
    text = "".join([c async for c in engine.stream([{"role": "user", "content": "hi"}])])
    assert "demo mode" in text.lower()


@pytest.mark.asyncio
async def test_local_engine_handles_question():
    engine = LocalEngine()
    text = "".join([c async for c in engine.stream([{"role": "user", "content": "How do I start?"}])])
    assert "approach" in text.lower()


@pytest.mark.asyncio
async def test_local_engine_handles_empty_history():
    engine = LocalEngine()
    text = "".join([c async for c in engine.stream([])])
    assert text.strip()


def test_get_engine_falls_back_to_local_without_key():
    # The test environment sets LLM_PROVIDER=local, so this must be the local engine.
    assert get_engine().name == "local-demo"
