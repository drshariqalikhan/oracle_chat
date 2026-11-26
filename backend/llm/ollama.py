from typing import Any

import httpx

from backend.llm.base import LLMProvider, LLMProviderError, LLMResponse


class OllamaProvider(LLMProvider):
    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        default_model: str = "",
        timeout: float = 120.0,
    ) -> None:
        self.base_url = base_url.strip().rstrip("/")
        self.default_model = default_model.strip()
        self.timeout = timeout

    async def chat(
        self,
        messages: list[dict[str, Any]],
        model: str | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        selected_model = (model or "").strip() or self.default_model
        if not selected_model or selected_model == "openrouter/free":
            raise LLMProviderError(
                "No Ollama model specified. Select a local model in Settings or set MODEL_NAME in .env.",
                status_code=400,
            )

        url = f"{self.base_url}/api/chat"
        payload: dict[str, Any] = {
            "model": selected_model,
            "messages": messages,
            "stream": False,
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
            mapped_status = response.status_code if response.status_code in (400, 404) else 502
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
            raise LLMResponse(
                content="Ollama returned an empty response.",
                model=str(data.get("model") or selected_model).strip(),
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
