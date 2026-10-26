"""Chat routes: streaming (SSE) and non-streaming completions."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user, rate_limit
from app.llm import get_engine
from app.models import Conversation, Message, User
from app.schemas import ChatRequest, ChatResponse, MessageOut

router = APIRouter(prefix="/api/chat", tags=["chat"], dependencies=[Depends(rate_limit)])

# How many prior messages to replay as context.
HISTORY_WINDOW = 20


def _load_conversation(db: Session, conversation_id: int, user: User) -> Conversation:
    conversation = db.get(Conversation, conversation_id)
    if conversation is None or conversation.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found.",
        )
    return conversation


def _build_context(conversation: Conversation) -> list[dict[str, str]]:
    """Turn stored messages into the provider's chat format."""
    history = conversation.messages[-HISTORY_WINDOW:]
    return [{"role": m.role, "content": m.content} for m in history]


def _persist_user_message(db: Session, conversation: Conversation, content: str) -> Message:
    message = Message(conversation_id=conversation.id, role="user", content=content)
    db.add(message)
    # First user message becomes the conversation title.
    if conversation.title in {"New chat", ""}:
        conversation.title = content[:60] + ("..." if len(content) > 60 else "")
    db.commit()
    db.refresh(message)
    return message


@router.post("/{conversation_id}", response_model=ChatResponse)
async def chat(
    conversation_id: int,
    payload: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ChatResponse:
    """Send a message and get the full assistant reply in one response."""
    conversation = _load_conversation(db, conversation_id, current_user)
    user_message = _persist_user_message(db, conversation, payload.content)

    engine = get_engine()
    context = _build_context(conversation)
    chunks: list[str] = []
    async for piece in engine.stream(context):
        chunks.append(piece)

    reply = "".join(chunks).strip() or "(no response)"
    assistant_message = Message(conversation_id=conversation.id, role="assistant", content=reply)
    db.add(assistant_message)
    db.commit()
    db.refresh(assistant_message)

    return ChatResponse(
        conversation_id=conversation.id,
        user_message=MessageOut.model_validate(user_message),
        assistant_message=MessageOut.model_validate(assistant_message),
    )


@router.post("/{conversation_id}/stream")
async def chat_stream(
    conversation_id: int,
    payload: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    """Send a message and stream the reply back as Server-Sent Events."""
    conversation = _load_conversation(db, conversation_id, current_user)
    user_message = _persist_user_message(db, conversation, payload.content)
    context = _build_context(conversation)
    engine = get_engine()
    conversation_id_value = conversation.id

    async def event_source():
        collected: list[str] = []
        yield f"data: {json.dumps({'type': 'start', 'user_message_id': user_message.id})}\n\n"
        try:
            async for piece in engine.stream(context):
                collected.append(piece)
                yield f"data: {json.dumps({'type': 'delta', 'content': piece})}\n\n"
        except Exception as exc:  # noqa: BLE001 - surface any engine failure to the client
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"

        reply = "".join(collected).strip() or "(no response)"
        # Persist on a fresh session: the request-scoped one is already closed
        # by the time a streaming body finishes.
        from app.database import SessionLocal

        with SessionLocal() as write_db:
            assistant = Message(conversation_id=conversation_id_value, role="assistant", content=reply)
            write_db.add(assistant)
            write_db.commit()
            write_db.refresh(assistant)
            assistant_id = assistant.id

        yield f"data: {json.dumps({'type': 'done', 'assistant_message_id': assistant_id})}\n\n"

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
