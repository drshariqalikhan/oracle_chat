from backend.config import Settings
from backend.llm.base import LLMProvider, LLMProviderError
from backend.llm.ollama import OllamaProvider
from backend.llm.openrouter import OpenRouterProvider

SUPPORTED_PROVIDERS = ("openrouter", "ollama")


def create_llm_provider(
    settings: Settings,
    provider_name: str | None = None,
    api_key: str | None = None,
    default_model: str | None = None,
    ollama_base_url: str | None = None,
) -> tuple[str, LLMProvider]:
    selected_provider = (provider_name or settings.llm_provider or "openrouter").strip().lower()

    if selected_provider == "openrouter":
        resolved_key = (api_key or "").strip() or settings.openrouter_api_key
        resolved_model = (default_model or "").strip() or settings.model_name or "openrouter/free"
        return selected_provider, OpenRouterProvider(
            api_key=resolved_key,
            default_model=resolved_model,
            base_url=settings.openrouter_base_url,
        )

    if selected_provider == "ollama":
        resolved_url = (ollama_base_url or "").strip().rstrip("/") or settings.ollama_base_url
        env_default = "" if settings.model_name == "openrouter/free" else settings.model_name
        resolved_model = (default_model or "").strip() or env_default
        return selected_provider, OllamaProvider(
            base_url=resolved_url,
            default_model=resolved_model,
            timeout=settings.ollama_timeout,
        )

    raise LLMProviderError(
        f"Unsupported LLM provider '{selected_provider}'. Supported providers: {', '.join(SUPPORTED_PROVIDERS)}.",
        status_code=400,
    )
