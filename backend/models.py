from pydantic import BaseModel, field_validator


class ChatRequest(BaseModel):
    message: str
    model: str | None = None
    pinned_model: str | None = None
    api_key: str | None = None

    @field_validator("message")
    @classmethod
    def message_must_not_be_empty(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Message cannot be empty.")
        return cleaned


class ChatResponse(BaseModel):
    reply: str
    model: str | None = None
    pinned: bool = False
