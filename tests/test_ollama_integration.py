import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
from fastapi.testclient import TestClient

from backend.llm.base import LLMProviderError
from backend.llm.ollama import OllamaProvider, normalize_ollama_base_url
from backend.main import app


class TestOllamaIntegration(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_cloudshell_preview_url_normalizes_to_loopback(self) -> None:
        url = "https://11434-cs-83875f3e-8b78-4232-a974-5df1e13506c4.cs-asia-southeast1-fork.cloudshell.dev"
        self.assertEqual(normalize_ollama_base_url(url), "http://127.0.0.1:11434")
        self.assertEqual(normalize_ollama_base_url("http://localhost:11434/"), "http://localhost:11434")

    def test_list_models_parses_ollama_tags(self) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "models": [
                {"name": "gemma3:4b", "size": 3300000000, "modified_at": "2026-11-01T00:00:00Z"},
                {"name": "qwen2.5-vl", "size": 5200000000, "modified_at": "2026-11-01T00:00:00Z"},
            ]
        }

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value.get = AsyncMock(return_value=mock_response)

        with patch("backend.llm.ollama.httpx.AsyncClient", return_value=mock_client):
            resp = self.client.get("/api/ollama/models")

        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["count"], 2)
        self.assertEqual(body["models"][0]["name"], "gemma3:4b")
        self.assertEqual(body["models"][1]["name"], "qwen2.5-vl")

    def test_invalid_ollama_url_returns_400(self) -> None:
        resp = self.client.get("/api/ollama/models?base_url=not-a-valid-url")
        self.assertEqual(resp.status_code, 400)

    def test_ollama_empty_content_raises_provider_error(self) -> None:
        provider = OllamaProvider(default_model="gemma3:4b")
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"model": "gemma3:4b", "message": {"content": "   "}}

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value.post = AsyncMock(return_value=mock_response)

        with patch("backend.llm.ollama.httpx.AsyncClient", return_value=mock_client):
            with self.assertRaises(LLMProviderError) as ctx:
                asyncio.run(provider.chat([{"role": "user", "content": "hi"}]))

        self.assertEqual(ctx.exception.status_code, 502)

    def test_ollama_404_suggests_pull_command(self) -> None:
        provider = OllamaProvider(default_model="gemma3:4b")
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.json.return_value = {"error": "model 'gemma3:4b' not found"}

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value.post = AsyncMock(return_value=mock_response)

        with patch("backend.llm.ollama.httpx.AsyncClient", return_value=mock_client):
            with self.assertRaises(LLMProviderError) as ctx:
                asyncio.run(provider.chat([{"role": "user", "content": "hi"}]))

        self.assertEqual(ctx.exception.status_code, 404)
        self.assertIn("ollama pull gemma3:4b", ctx.exception.message)

    def test_ollama_unreachable_raises_502(self) -> None:
        provider = OllamaProvider(base_url="http://localhost:11434", default_model="gemma3:4b")
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value.post = AsyncMock(
            side_effect=httpx.ConnectError("Connection refused")
        )

        with patch("backend.llm.ollama.httpx.AsyncClient", return_value=mock_client):
            with self.assertRaises(LLMProviderError) as ctx:
                asyncio.run(provider.chat([{"role": "user", "content": "hi"}]))

        self.assertEqual(ctx.exception.status_code, 502)


if __name__ == "__main__":
    unittest.main()
