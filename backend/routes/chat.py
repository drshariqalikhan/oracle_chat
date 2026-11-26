from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

from backend.config import get_settings
from backend.llm.base import LLMProviderError
from backend.llm.openrouter import OpenRouterProvider
from backend.models import ChatHistoryResponse, ChatRequest, ChatResponse, StandardizedLLMOutput
from backend.services.a2ui_service import ALL_BASIC_COMPONENTS, A2uiService
from backend.services.file_service import FileService, FileValidationError
from backend.services.image_service import ImageService, ImageValidationError
from backend.services.memory_service import MemoryService

router = APIRouter(tags=["chat"])

FREE_ROUTER_MODEL = "openrouter/free"
RETRIABLE_PIN_STATUSES = {400, 404, 429, 502, 503, 504}
UPLOADS_DIR = Path(__file__).resolve().parent.parent.parent / "uploads"

_pinned_free_model: str | None = None
_pinned_vision_model: str | None = None

memory_service = MemoryService(max_messages=40)
image_service = ImageService(uploads_dir=UPLOADS_DIR)
file_service = FileService(uploads_dir=UPLOADS_DIR)
a2ui_service = A2uiService()


@router.get("/chat/pinned-model")
async def get_pinned_model() -> dict[str, str | None]:
    return {
        "pinned_model": _pinned_free_model,
        "pinned_vision_model": _pinned_vision_model,
    }


@router.post("/chat/reset-model")
async def reset_pinned_model() -> dict[str, str | None]:
    global _pinned_free_model, _pinned_vision_model
    _pinned_free_model = None
    _pinned_vision_model = None
    return {
        "status": "ok",
        "pinned_model": None,
        "pinned_vision_model": None,
    }


@router.get("/api/a2ui/showcase")
async def get_a2ui_showcase() -> dict[str, Any]:
    output = a2ui_service.get_showcase_output()
    return {
        "status": "ok",
        "components_supported": list(ALL_BASIC_COMPONENTS),
        "component_count": len(ALL_BASIC_COMPONENTS),
        "output": output.model_dump(),
    }


@router.get("/chat/history/{session_id}", response_model=ChatHistoryResponse)
async def get_chat_history(session_id: str) -> ChatHistoryResponse:
    cleaned_id = session_id.strip()
    if not cleaned_id:
        raise HTTPException(status_code=400, detail="Session ID cannot be empty.")
    return ChatHistoryResponse(
        session_id=cleaned_id,
        messages=memory_service.get_history(cleaned_id),
    )


@router.delete("/chat/history/{session_id}")
async def clear_chat_history(session_id: str) -> dict[str, str]:
    cleaned_id = session_id.strip()
    if not cleaned_id:
        raise HTTPException(status_code=400, detail="Session ID cannot be empty.")
    memory_service.clear_session(cleaned_id)
    return {"status": "ok", "session_id": cleaned_id}


@router.post("/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest) -> ChatResponse:
    global _pinned_free_model, _pinned_vision_model

    settings = get_settings()
    api_key = (payload.api_key or "").strip() or settings.openrouter_api_key
    requested_model = (payload.model or "").strip() or settings.model_name or FREE_ROUTER_MODEL
    session_id = (payload.session_id or "").strip() or memory_service.create_session_id()

    provider = OpenRouterProvider(
        api_key=api_key,
        default_model=FREE_ROUTER_MODEL,
        base_url=settings.openrouter_base_url,
    )

    is_vision = bool(payload.image_id)
    image_data_url: str | None = None

    if payload.image_id:
        try:
            image_data_url = image_service.load_image_as_data_url(payload.image_id)
        except ImageValidationError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    if payload.document_id:
        try:
            doc_text, _, _ = file_service.extract_text_by_id(payload.document_id)
        except FileValidationError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

        doc_display_name = payload.document_name or payload.document_id
        memory_service.attach_document(
            session_id=session_id,
            file_id=payload.document_id,
            filename=doc_display_name,
            text=doc_text,
        )

    prior_messages = memory_service.get_history(session_id)
    documents_context = memory_service.get_documents_context(session_id)
    has_document_context = bool(documents_context)
    a2ui_system_prompt = a2ui_service.build_system_prompt(payload.ui_mode)

    base_history: list[dict[str, Any]] = []
    if a2ui_system_prompt:
        base_history.append({"role": "system", "content": a2ui_system_prompt})
    base_history.extend(prior_messages)

    async def run_inference(target_model: str):
        if is_vision and image_data_url is not None:
            vision_history = list(base_history)
            if documents_context:
                vision_history.append(
                    {
                        "role": "user",
                        "content": f"Uploaded document context:\n\n{documents_context}",
                    }
                )
            return await provider.analyze_image(
                prompt=payload.message,
                image_data_url=image_data_url,
                history=vision_history,
                model=target_model,
            )

        if documents_context:
            return await provider.process_document(
                prompt=payload.message,
                document_context=documents_context,
                history=base_history,
                model=target_model,
            )

        return await provider.chat(
            messages=[*base_history, {"role": "user", "content": payload.message}],
            model=target_model,
        )

    memory_prefixes: list[str] = []
    if payload.image_id:
        memory_prefixes.append(f"[Uploaded image: {payload.image_id}]")
    if payload.document_id:
        memory_prefixes.append(
            f"[Uploaded document: {payload.document_name or payload.document_id}]"
        )
    memory_user_text = (
        f"{' '.join(memory_prefixes)} {payload.message}"
        if memory_prefixes
        else payload.message
    )

    if requested_model == FREE_ROUTER_MODEL:
        if is_vision:
            active_pinned = (payload.pinned_vision_model or "").strip() or _pinned_vision_model
        else:
            active_pinned = (payload.pinned_model or "").strip() or _pinned_free_model

        target_model = active_pinned or FREE_ROUTER_MODEL

        try:
            result = await run_inference(target_model)
        except LLMProviderError as exc:
            if target_model != FREE_ROUTER_MODEL and exc.status_code in RETRIABLE_PIN_STATUSES:
                if is_vision:
                    _pinned_vision_model = None
                else:
                    _pinned_free_model = None
                try:
                    result = await run_inference(FREE_ROUTER_MODEL)
                except LLMProviderError as retry_exc:
                    raise HTTPException(
                        status_code=retry_exc.status_code,
                        detail=retry_exc.message,
                    ) from retry_exc
            else:
                raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

        if result.model and result.model != FREE_ROUTER_MODEL:
            if is_vision:
                _pinned_vision_model = result.model
            else:
                _pinned_free_model = result.model

        standardized: StandardizedLLMOutput = a2ui_service.parse_and_standardize(
            result.content,
            ui_mode=payload.ui_mode,
        )

        updated_history = memory_service.append_turn(
            session_id=session_id,
            user_message=memory_user_text,
            assistant_reply=standardized.text,
        )

        return ChatResponse(
            reply=standardized.text,
            output=standardized,
            session_id=session_id,
            history_length=len(updated_history),
            model=result.model,
            pinned=bool(_pinned_vision_model if is_vision else _pinned_free_model),
            vision_used=is_vision,
            document_used=has_document_context,
        )

    try:
        result = await run_inference(requested_model)
    except LLMProviderError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    standardized = a2ui_service.parse_and_standardize(
        result.content,
        ui_mode=payload.ui_mode,
    )

    updated_history = memory_service.append_turn(
        session_id=session_id,
        user_message=memory_user_text,
        assistant_reply=standardized.text,
    )

    return ChatResponse(
        reply=standardized.text,
        output=standardized,
        session_id=session_id,
        history_length=len(updated_history),
        model=result.model,
        pinned=False,
        vision_used=is_vision,
        document_used=has_document_context,
    )
