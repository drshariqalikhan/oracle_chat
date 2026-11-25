from typing import Any

import httpx

from backend.llm.base import LLMProvider, LLMProviderError, LLMResponse


class OpenRouterProvider(LLMProvider):
    def __init__(
        self,
        api_key: str,
        default_model: str = "openrouter/free",
        base_url: str = "https://openrouter.ai/api/v1",
        timeout: float = 90.0,
    ) -> None:
        self.api_key = api_key.strip()
        self.default_model = default_model.strip()
        self.base_url = base_url.strip().rstrip("/")
        self.timeout = timeout

    async def chat(
        self,
        messages: list[dict[str, Any]],
        model: str | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        if not self.api_key:
            raise LLMProviderError(
                "OpenRouter API key is missing. Set OPENROUTER_API_KEY in .env or enter it in Settings.",
                status_code=400,
            )

        selected_model = (model or "").strip() or self.default_model
        if not selected_model:
            raise LLMProviderError("No OpenRouter model specified.", status_code=400)

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/drshariqalikhan/oracle_chat",
            "X-Title": "ORACLE CHAT",
        }
        payload: dict[str, Any] = {
            "model": selected_model,
            "messages": messages,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, headers=headers, json=payload)
        except httpx.TimeoutException as exc:
            raise LLMProviderError(
                f"Timed out waiting for OpenRouter response (model: {selected_model}).",
                status_code=504,
            ) from exc
        except httpx.RequestError as exc:
            raise LLMProviderError(
                f"Network error contacting OpenRouter: {exc}",
                status_code=502,
            ) from exc

        if response.status_code >= 400:
            detail = self._extract_error_detail(response)
            mapped_status = (
                response.status_code
                if response.status_code in (400, 401, 402, 403, 404, 429)
                else 502
            )
            raise LLMProviderError(
                f"OpenRouter error ({response.status_code}): {detail}",
                status_code=mapped_status,
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise LLMProviderError("Invalid JSON response received from OpenRouter.", status_code=502) from exc

        choices = data.get("choices") or []
        if not choices:
            raise LLMProviderError("OpenRouter returned no choices in response.", status_code=502)

        message_obj = choices[0].get("message") or {}
        content = message_obj.get("content")

        if isinstance(content, list):
            text_parts = [
                part.get("text", "")
                for part in content
                if isinstance(part, dict) and part.get("type") == "text"
            ]
            content = "\n".join(part for part in text_parts if part)

        if not isinstance(content, str) or not content.strip():
            raise LLMProviderError("OpenRouter returned an empty message.", status_code=502)

        assigned_model = str(data.get("model") or selected_model).strip()
        return LLMResponse(content=content.strip(), model=assigned_model)

    async def analyze_image(
        self,
        prompt: str,
        image_data_url: str,
        history: list[dict[str, Any]] | None = None,
        model: str | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        multimodal_message = {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": image_data_url}},
            ],
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
            if isinstance(data, dict):
                err = data.get("error")
                if isinstance(err, dict) and err.get("message"):
                    return str(err["message"])
                if data.get("message"):
                    return str(data["message"])
        except ValueError:
            pass
        return response.text.strip() or f"HTTP {response.status_code}"
