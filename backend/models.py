from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class A2uiActionPayload(BaseModel):
    name: str
    surface_id: str = "main"
    source_component_id: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)


class StandardizedLLMOutput(BaseModel):
    text: str
    a2ui_messages: list[dict[str, Any]] = Field(default_factory=list)
    used_a2ui: bool = False
    ui_mode: Literal["auto", "a2ui", "text"] = "auto"
    raw_format: Literal["express", "wire_json", "text"] = "text"
    repair_retried: bool = False
    validation_warnings: list[str] = Field(default_factory=list)


class ChatRequest(BaseModel):
    message: str = ""
    session_id: str | None = None
    image_id: str | None = None
    document_id: str | None = None
    document_name: str | None = None
    ui_mode: Literal["auto", "a2ui", "text"] = "auto"
    a2ui_action: A2uiActionPayload | None = None
    provider: str | None = None
    model: str | None = None
    pinned_model: str | None = None
    pinned_vision_model: str | None = None
    api_key: str | None = None
    ollama_base_url: str | None = None

    @model_validator(mode="after")
    def validate_message_or_attachment(self) -> "ChatRequest":
        cleaned_msg = self.message.strip()
        cleaned_img = (self.image_id or "").strip() or None
        cleaned_doc = (self.document_id or "").strip() or None

        if not cleaned_msg and not cleaned_img and not cleaned_doc and not self.a2ui_action:
            raise ValueError("A message, image_id, document_id, or a2ui_action is required.")

        if not cleaned_msg:
            if self.a2ui_action:
                cleaned_msg = (
                    f"User triggered A2UI action '{self.a2ui_action.name}' on surface "
                    f"'{self.a2ui_action.surface_id}' with context: {self.a2ui_action.context}"
                )
            elif cleaned_img:
                cleaned_msg = "Describe this image in detail."
            elif cleaned_doc:
                cleaned_msg = "Summarize this document and list its key points."

        self.message = cleaned_msg
        self.image_id = cleaned_img
        self.document_id = cleaned_doc
        self.document_name = (self.document_name or "").strip() or None
        self.provider = (self.provider or "").strip().lower() or None
        self.ollama_base_url = (self.ollama_base_url or "").strip().rstrip("/") or None
        return self


class ChatResponse(BaseModel):
    reply: str
    output: StandardizedLLMOutput
    session_id: str
    history_length: int
    provider: str
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
