import os
import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from backend.config import get_settings
from backend.llm.base import LLMProvider, LLMProviderError, LLMResponse
from backend.llm.factory import create_llm_provider
from backend.llm.ollama import OllamaProvider
from backend.llm.openrouter import OpenRouterProvider
from backend.main import app


class TestProviderAbstraction(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_factory_creates_openrouter_and_ollama_providers(self) -> None:
        settings = get_settings()
        name_or, prov_or = create_llm_provider(settings, provider_name="openrouter", api_key="k")
        self.assertEqual(name_or, "openrouter")
        self.assertIsInstance(prov_or, OpenRouterProvider)
        self.assertIsInstance(prov_or, LLMProvider)

        name_ol, prov_ol = create_llm_provider(settings, provider_name="ollama", default_model="gemma3:4b")
        self.assertEqual(name_ol, "ollama")
        self.assertIsInstance(prov_ol, OllamaProvider)
        self.assertIsInstance(prov_ol, LLMProvider)

    def test_factory_rejects_unknown_provider(self) -> None:
        settings = get_settings()
        with self.assertRaises(LLMProviderError) as ctx:
            create_llm_provider(settings, provider_name="unknown_llm")
        self.assertEqual(ctx.exception.status_code, 400)

    def test_chat_routes_via_ollama_when_configured_by_env(self) -> None:
        mock_reply = LLMResponse(content="Hello from local Ollama!", model="gemma3:4b")
        with patch.dict(os.environ, {"LLM_PROVIDER": "ollama", "MODEL_NAME": "gemma3:4b"}):
            with patch("backend.llm.ollama.OllamaProvider.chat", new=AsyncMock(return_value=mock_reply)):
                resp = self.client.post(
                    "/chat",
                    json={"message": "Hi", "ui_mode": "text"},
                )

        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["provider"], "ollama")
        self.assertEqual(body["model"], "gemma3:4b")
        self.assertEqual(body["reply"], "Hello from local Ollama!")

    def test_chat_routes_via_openrouter_when_configured_by_env(self) -> None:
        mock_reply = LLMResponse(content="Hello from OpenRouter!", model="test/model:free")
        with patch.dict(os.environ, {"LLM_PROVIDER": "openrouter", "OPENROUTER_API_KEY": "test-key"}):
            with patch("backend.llm.openrouter.OpenRouterProvider.chat", new=AsyncMock(return_value=mock_reply)):
                resp = self.client.post(
                    "/chat",
                    json={"message": "Hi", "ui_mode": "text"},
                )

        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["provider"], "openrouter")
        self.assertEqual(body["reply"], "Hello from OpenRouter!")

    def test_ollama_analyze_image_strips_data_url_prefix(self) -> None:
        provider = OllamaProvider(default_model="qwen2.5-vl")
        captured = {}

        async def fake_chat(messages, model=None, **kwargs):
            captured["messages"] = messages
            captured["model"] = model
            return LLMResponse(content="A red square.", model="qwen2.5-vl")

        with patch.object(provider, "chat", side_effect=fake_chat):
            import asyncio
            res = asyncio.run(
                provider.analyze_image(
                    prompt="What is this?",
                    image_data_url="data:image/png;base64,QUJDREVGRw==",
                )
            )

        self.assertEqual(res.content, "A red square.")
        self.assertEqual(captured["messages"][-1]["images"], ["QUJDREVGRw=="])


if __name__ == "__main__":
    unittest.main()
