import re
from typing import Any
from urllib.parse import urlparse

import httpx

from backend.llm.base import LLMProvider, LLMProviderError, LLMResponse

CLOUDSHELL_PREVIEW_RE = re.compile(
    r"^https?://(\d+)-cs-[^/]+\.cloudshell\.dev(?:/.*)?$",
    re.IGNORECASE,
)


def normalize_ollama_base_url(base_url: str) -> str:
    cleaned = (base_url or "").strip().rstrip("/")
    match = CLOUDSHELL_PREVIEW_RE.match(cleaned)
    if match:
        port = match.group(1)
        return f"http://127.0.0.1:{port}"
    return cleaned


class OllamaProvider(LLMProvider):
    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        default_model: str = "",
        timeout: float = 300.0,
    ) -> None:
        self.base_url = normalize_ollama_base_url(base_url or "http://localhost:11434")
        self.default_model = default_model.strip()
        self.timeout = timeout

    def _validate_base_url(self) -> None:
        parsed = urlparse(self.base_url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise LLMProviderError(
                f"Invalid Ollama URL: '{self.base_url}'. Must start with http:// or https://",
                status_code=400,
            )

    async def list_models(self) -> list[dict[str, Any]]:
        self._validate_base_url()
        tags_url = f"{self.base_url}/api/tags"

        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                response = await client.get(tags_url, headers={"Accept": "application/json"})
        except httpx.TimeoutException as exc:
            raise LLMProviderError(
                f"Timed out connecting to Ollama at {self.base_url}",
                status_code=504,
            ) from exc
        except httpx.RequestError as exc:
            raise LLMProviderError(
                f"Cannot reach Ollama at {self.base_url} ({exc})",
                status_code=502,
            ) from exc

        if response.status_code >= 400:
            detail = self._extract_error_detail(response)
            raise LLMProviderError(
                f"Ollama returned HTTP {response.status_code} at {tags_url}: {detail}",
                status_code=502,
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise LLMProviderError(
                f"Invalid JSON received from Ollama at {tags_url}.",
                status_code=502,
            ) from exc

        raw_models = payload.get("models", [])
        return [
            {
                "name": item.get("name", ""),
                "size": item.get("size", 0),
                "modified_at": item.get("modified_at", ""),
                "details": item.get("details", {}),
            }
            for item in raw_models
            if item.get("name")
        ]

    async def _auto_detect_model(self) -> str:
        models = await self.list_models()
        if not models:
            raise LLMProviderError(
                "No local Ollama models installed. Run `sudo ollama pull <model_name>` on your VM.",
                status_code=400,
            )
        return models[0]["name"]

    async def chat(
        self,
        messages: list[dict[str, Any]],
        model: str | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        self._validate_base_url()
        selected_model = (model or "").strip() or self.default_model
        if not selected_model or selected_model == "openrouter/free":
            selected_model = await self._auto_detect_model()

        url = f"{self.base_url}/api/chat"
        payload: dict[str, Any] = {
            "model": selected_model,
            "messages": messages,
            "stream": False,
            "think": False,  # <--- DISBLES DEEP REASONING / CHAIN OF THOUGHT
            "options": {
                "num_ctx": 4096,
            },
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload)
        except httpx.TimeoutException as exc:
            raise LLMProviderError(
                f"Timed out waiting for Ollama response at {self.base_url} (model: {selected_model}).",
                status_code=504,
            ) from exc
        except httpx.RequestError as exc:
            raise LLMProviderError(
                f"Cannot reach Ollama at {self.base_url}: {exc}",
                status_code=502,
            ) from exc

        if response.status_code >= 400:
            detail = self._extract_error_detail(response)
            if response.status_code == 404:
                raise LLMProviderError(
                    f"Ollama model '{selected_model}' not found ({detail}). Run: ollama pull {selected_model}",
                    status_code=404,
                )
            mapped_status = 400 if response.status_code == 400 else 502
            raise LLMProviderError(
                f"Ollama error ({response.status_code}): {detail}",
                status_code=mapped_status,
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise LLMProviderError(
                f"Invalid JSON response received from Ollama at {self.base_url}.",
                status_code=502,
            ) from exc

        message_obj = data.get("message") or {}
        content = message_obj.get("content")
        if not isinstance(content, str) or not content.strip():
            raise LLMProviderError(
                f"Ollama returned an empty response for model '{selected_model}'.",
                status_code=502,
            )

        resolved_model = str(data.get("model") or selected_model).strip()
        return LLMResponse(content=content.strip(), model=resolved_model)

    async def analyze_image(
        self,
        prompt: str,
        image_data_url: str,
        history: list[dict[str, Any]] | None = None,
        model: str | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        raw_base64 = (
            image_data_url.split(",", 1)[1]
            if "," in image_data_url
            else image_data_url
        )
        multimodal_message = {
            "role": "user",
            "content": prompt,
            "images": [raw_base64],
        }
        messages = [*(history or []), multimodal_message]
        return await self.chat(messages=messages, model=model, **kwargs)

    async def process_document(
        self,
        prompt: str,
        document_context: str,
        history: list[dict[str, Any]] | None = None,
        model: str | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        context_instruction = {
            "role": "user",
            "content": (
                "Use the following uploaded document content to answer the user's questions accurately. "
                "If the answer is not in the document, say so clearly.\n\n"
                f"{document_context}"
            ),
        }
        messages = [
            context_instruction,
            *(history or []),
            {"role": "user", "content": prompt},
        ]
        return await self.chat(messages=messages, model=model, **kwargs)

    @staticmethod
    def _extract_error_detail(response: httpx.Response) -> str:
        try:
            data = response.json()
            if isinstance(data, dict) and data.get("error"):
                return str(data["error"])
        except ValueError:
            pass
        return response.text.strip() or f"HTTP {response.status_code}"
