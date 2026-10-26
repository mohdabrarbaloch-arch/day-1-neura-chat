"""Pydantic request/response schemas (the public API contract)."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


# --- Auth ------------------------------------------------------------------
class UserRegister(BaseModel):
    email: EmailStr
    display_name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("display_name")
    @classmethod
    def _strip_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("display_name must not be blank")
        return cleaned


class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    display_name: str
    created_at: datetime


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut


# --- Conversations ---------------------------------------------------------
class ConversationCreate(BaseModel):
    title: str = Field(default="New chat", max_length=200)
    model: str = Field(default="default", max_length=80)

    @field_validator("title")
    @classmethod
    def _clean_title(cls, value: str) -> str:
        cleaned = value.strip()
        return cleaned or "New chat"


class ConversationUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    role: str
    content: str
    created_at: datetime


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    model: str
    created_at: datetime
    updated_at: datetime


class ConversationDetail(ConversationOut):
    messages: list[MessageOut] = Field(default_factory=list)


# --- Chat ------------------------------------------------------------------
class ChatRequest(BaseModel):
    content: str = Field(min_length=1, max_length=8000)
    stream: bool = True

    @field_validator("content")
    @classmethod
    def _strip_content(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("content must not be blank")
        return cleaned


class ChatResponse(BaseModel):
    conversation_id: int
    user_message: MessageOut
    assistant_message: MessageOut


class HealthOut(BaseModel):
    status: str
    app: str
    version: str
    environment: str
    llm_provider: str
    database: str
