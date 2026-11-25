from pydantic import BaseModel, field_validator


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None
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
    session_id: str
    history_length: int
    model: str | None = None
    pinned: bool = False


class ChatHistoryResponse(BaseModel):
    session_id: str
    messages: list[dict[str, str]]


class ImageUploadResponse(BaseModel):
    status: str
    file_id: str
    original_filename: str
    url: str
    content_type: str
    size_bytes: int
    width: int
    height: int
