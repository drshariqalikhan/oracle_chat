from pydantic import BaseModel, model_validator


class ChatRequest(BaseModel):
    message: str = ""
    session_id: str | None = None
    image_id: str | None = None
    model: str | None = None
    pinned_model: str | None = None
    pinned_vision_model: str | None = None
    api_key: str | None = None

    @model_validator(mode="after")
    def validate_message_or_image(self) -> "ChatRequest":
        cleaned_msg = self.message.strip()
        cleaned_img = (self.image_id or "").strip() or None

        if not cleaned_msg and not cleaned_img:
            raise ValueError("Either a message or an uploaded image_id is required.")

        self.message = cleaned_msg or "Describe this image in detail."
        self.image_id = cleaned_img
        return self


class ChatResponse(BaseModel):
    reply: str
    session_id: str
    history_length: int
    model: str | None = None
    pinned: bool = False
    vision_used: bool = False


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
