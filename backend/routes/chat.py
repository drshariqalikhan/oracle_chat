from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from backend.config import get_settings
from backend.llm.base import LLMProvider, LLMProviderError, LLMResponse
from backend.llm.factory import SUPPORTED_PROVIDERS, create_llm_provider
from backend.llm.ollama import OllamaProvider
from backend.models import (
    ChatHistoryResponse,
    ChatRequest,
    ChatResponse,
    SessionListResponse,
    SessionSummary,
    StandardizedLLMOutput,
)
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

memory_service = MemoryService()
image_service = ImageService(uploads_dir=UPLOADS_DIR)
file_service = FileService(uploads_dir=UPLOADS_DIR)
a2ui_service = A2uiService()


@router.get("/api/providers")
async def get_provider_config() -> dict[str, Any]:
    settings = get_settings()
    return {
        "active_provider": settings.llm_provider,
        "default_model": settings.model_name,
        "ollama_base_url": settings.ollama_base_url,
        "openrouter_configured": bool(settings.openrouter_api_key),
        "supported_providers": list(SUPPORTED_PROVIDERS),
    }


@router.get("/chat/sessions", response_model=SessionListResponse)
async def list_chat_sessions() -> SessionListResponse:
    raw_list = memory_service.list_sessions()
    summaries = [SessionSummary(**item) for item in raw_list]
    return SessionListResponse(sessions=summaries)


@router.post("/chat/sessions")
async def create_new_session() -> dict[str, str]:
    session_id = memory_service.create_session_id()
    memory_service.ensure_session(session_id, title="New Chat")
    return {"status": "ok", "session_id": session_id, "title": "New Chat"}


@router.delete("/chat/sessions/{session_id}")
async def delete_chat_session(session_id: str) -> dict[str, str]:
    cleaned_id = session_id.strip()
    if not cleaned_id:
        raise HTTPException(status_code=400, detail="Session ID cannot be empty.")
    memory_service.clear_session(cleaned_id)
    return {"status": "ok", "session_id": cleaned_id}


@router.get("/api/ollama/models")
async def discover_ollama_models(
    base_url: str | None = Query(default=None),
) -> dict[str, Any]:
    settings = get_settings()
    target_url = (base_url or settings.ollama_base_url).strip().rstrip("/")
    provider = OllamaProvider(base_url=target_url)

    try:
        models = await provider.list_models()
    except LLMProviderError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    return {
        "status": "ok",
        "base_url": target_url,
        "count": len(models),
        "models": models,
    }


@router.get("/api/ollama/health")
async def check_ollama_health(
    base_url: str | None = Query(default=None),
) -> dict[str, Any]:
    settings = get_settings()
    target_url = (base_url or settings.ollama_base_url).strip().rstrip("/")
    provider = OllamaProvider(base_url=target_url)

    try:
        models = await provider.list_models()
    except LLMProviderError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    return {
        "status": "online",
        "base_url": target_url,
        "installed_models": len(models),
    }


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
    info = memory_service.get_session_info(cleaned_id)
    title = info["title"] if info else "Chat"
    return ChatHistoryResponse(
        session_id=cleaned_id,
        title=title,
        messages=memory_service.get_history(cleaned_id),
    )


@router.delete("/chat/history/{session_id}")
async def clear_chat_history(session_id: str) -> dict[str, str]:
    cleaned_id = session_id.strip()
    if not cleaned_id:
        raise HTTPException(status_code=400, detail="Session ID cannot be empty.")
    memory_service.clear_session(cleaned_id)
    return {"status": "ok", "session_id": cleaned_id}


async def _parse_with_optional_repair(
    provider: LLMProvider,
    initial_result: LLMResponse,
    base_history: list[dict[str, Any]],
    user_prompt: str,
    ui_mode: str,
) -> tuple[StandardizedLLMOutput, LLMResponse]:
    standardized = a2ui_service.parse_and_standardize(
        initial_result.content,
        ui_mode=ui_mode,
    )

    if ui_mode == "text" or standardized.used_a2ui or not standardized.validation_warnings:
        return standardized, initial_result

    repair_messages = [
        *base_history,
        {"role": "user", "content": user_prompt},
        {"role": "assistant", "content": initial_result.content},
        {"role": "user", "content": a2ui_service.build_repair_prompt(standardized.validation_warnings)},
    ]

    try:
        repaired_result = await provider.chat(
            messages=repair_messages,
            model=initial_result.model,
        )
    except LLMProviderError:
        return standardized, initial_result

    repaired_standardized = a2ui_service.parse_and_standardize(
        repaired_result.content,
        ui_mode=ui_mode,
    )
    repaired_standardized = repaired_standardized.model_copy(update={"repair_retried": True})

    if repaired_standardized.used_a2ui:
        return repaired_standardized, repaired_result

    combined_warnings = [
        *standardized.validation_warnings,
        *repaired_standardized.validation_warnings,
    ]
    return (
        repaired_standardized.model_copy(update={"validation_warnings": combined_warnings}),
        repaired_result,
    )


@router.post("/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest) -> ChatResponse:
    global _pinned_free_model, _pinned_vision_model

    settings = get_settings()
    session_id = (payload.session_id or "").strip() or memory_service.create_session_id()
    memory_service.ensure_session(session_id)

    try:
        active_provider, provider = create_llm_provider(
            settings=settings,
            provider_name=payload.provider,
            api_key=payload.api_key,
            default_model=payload.model,
            ollama_base_url=payload.ollama_base_url,
        )
    except LLMProviderError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    if active_provider == "openrouter":
        requested_model = (payload.model or "").strip() or settings.model_name or FREE_ROUTER_MODEL
    else:
        env_ollama_model = "" if settings.model_name == FREE_ROUTER_MODEL else settings.model_name
        requested_model = (payload.model or "").strip() or env_ollama_model

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
    if active_provider == "ollama":
        prior_messages = prior_messages[-4:]

    documents_context = memory_service.get_documents_context(session_id)
    has_document_context = bool(documents_context)

    a2ui_system_prompt = a2ui_service.build_system_prompt(
        payload.ui_mode,
        provider=active_provider,
    )

    base_history: list[dict[str, Any]] = []
    if a2ui_system_prompt:
        base_history.append({"role": "system", "content": a2ui_system_prompt})
    base_history.extend(prior_messages)

    async def run_inference(target_model: str | None) -> LLMResponse:
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

    if active_provider == "openrouter" and requested_model == FREE_ROUTER_MODEL:
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

        standardized, final_result = await _parse_with_optional_repair(
            provider=provider,
            initial_result=result,
            base_history=base_history,
            user_prompt=payload.message,
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
            provider=active_provider,
            model=final_result.model,
            pinned=bool(_pinned_vision_model if is_vision else _pinned_free_model),
            vision_used=is_vision,
            document_used=has_document_context,
        )

    try:
        result = await run_inference(requested_model or None)
    except LLMProviderError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    standardized, final_result = await _parse_with_optional_repair(
        provider=provider,
        initial_result=result,
        base_history=base_history,
        user_prompt=payload.message,
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
        provider=active_provider,
        model=final_result.model,
        pinned=False,
        vision_used=is_vision,
        document_used=has_document_context,
    )
