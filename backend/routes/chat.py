from fastapi import APIRouter, HTTPException

from backend.config import get_settings
from backend.llm.base import LLMProviderError
from backend.llm.openrouter import OpenRouterProvider
from backend.models import ChatHistoryResponse, ChatRequest, ChatResponse
from backend.services.memory_service import MemoryService

router = APIRouter(tags=["chat"])

FREE_ROUTER_MODEL = "openrouter/free"
RETRIABLE_PIN_STATUSES = {404, 429, 502, 503, 504}

_pinned_free_model: str | None = None
memory_service = MemoryService(max_messages=40)


@router.get("/chat/pinned-model")
async def get_pinned_model() -> dict[str, str | None]:
    return {"pinned_model": _pinned_free_model}


@router.post("/chat/reset-model")
async def reset_pinned_model() -> dict[str, str | None]:
    global _pinned_free_model
    _pinned_free_model = None
    return {"status": "ok", "pinned_model": None}


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
    global _pinned_free_model

    settings = get_settings()
    api_key = (payload.api_key or "").strip() or settings.openrouter_api_key
    requested_model = (payload.model or "").strip() or settings.model_name or FREE_ROUTER_MODEL
    session_id = (payload.session_id or "").strip() or memory_service.create_session_id()

    provider = OpenRouterProvider(
        api_key=api_key,
        default_model=FREE_ROUTER_MODEL,
        base_url=settings.openrouter_base_url,
    )

    prior_messages = memory_service.get_history(session_id)
    messages = [*prior_messages, {"role": "user", "content": payload.message}]

    if requested_model == FREE_ROUTER_MODEL:
        active_pinned = (payload.pinned_model or "").strip() or _pinned_free_model
        target_model = active_pinned or FREE_ROUTER_MODEL

        try:
            result = await provider.chat(messages=messages, model=target_model)
        except LLMProviderError as exc:
            if target_model != FREE_ROUTER_MODEL and exc.status_code in RETRIABLE_PIN_STATUSES:
                _pinned_free_model = None
                try:
                    result = await provider.chat(messages=messages, model=FREE_ROUTER_MODEL)
                except LLMProviderError as retry_exc:
                    raise HTTPException(
                        status_code=retry_exc.status_code,
                        detail=retry_exc.message,
                    ) from retry_exc
            else:
                raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

        if result.model and result.model != FREE_ROUTER_MODEL:
            _pinned_free_model = result.model

        updated_history = memory_service.append_turn(
            session_id=session_id,
            user_message=payload.message,
            assistant_reply=result.content,
        )

        return ChatResponse(
            reply=result.content,
            session_id=session_id,
            history_length=len(updated_history),
            model=result.model,
            pinned=bool(_pinned_free_model),
        )

    try:
        result = await provider.chat(messages=messages, model=requested_model)
    except LLMProviderError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    updated_history = memory_service.append_turn(
        session_id=session_id,
        user_message=payload.message,
        assistant_reply=result.content,
    )

    return ChatResponse(
        reply=result.content,
        session_id=session_id,
        history_length=len(updated_history),
        model=result.model,
        pinned=False,
    )
