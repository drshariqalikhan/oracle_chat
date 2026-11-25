from pydantic import BaseModel, model_validator


class ChatRequest(BaseModel):
    message: str = ""
    session_id: str | None = None
    image_id: str | None = None
    document_id: str | None = None
    document_name: str | None = None
    model: str | None = None
    pinned_model: str | None = None
    pinned_vision_model: str | None = None
    api_key: str | None = None

    @model_validator(mode="after")
    def validate_message_or_attachment(self) -> "ChatRequest":
        cleaned_msg = self.message.strip()
        cleaned_img = (self.image_id or "").strip() or None
        cleaned_doc = (self.document_id or "").strip() or None

        if not cleaned_msg and not cleaned_img and not cleaned_doc:
            raise ValueError("A message, image_id, or document_id is required.")

        if not cleaned_msg:
            if cleaned_img:
                cleaned_msg = "Describe this image in detail."
            elif cleaned_doc:
                cleaned_msg = "Summarize this document and list its key points."

        self.message = cleaned_msg
        self.image_id = cleaned_img
        self.document_id = cleaned_doc
        self.document_name = (self.document_name or "").strip() or None
        return self


class ChatResponse(BaseModel):
    reply: str
    session_id: str
    history_length: int
    model: str | None = None
    pinned: bool = False
    vision_used: bool = False
    document_used: bool = False


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


class DocumentUploadResponse(BaseModel):
    status: str
    file_id: str
    original_filename: str
    file_type: str
    size_bytes: int
    page_count: int
    char_count: int
    truncated: bool
    preview: str
