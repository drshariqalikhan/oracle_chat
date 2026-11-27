import asyncio
import os
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from trends_pipeline.fetcher import fetch_trends_data, resolve_env_placeholders
from trends_pipeline.models import TrendsPipelineConfig


class TestTrendsPipeline(unittest.TestCase):
    def test_google_trends_config_validates(self) -> None:
        cfg_path = Path("configs/google_trends_pipeline.json")
        cfg = TrendsPipelineConfig.model_validate_json(cfg_path.read_text(encoding="utf-8"))
        self.assertEqual(cfg.pipeline_name, "Google Trends Monitor")
        self.assertEqual(cfg.api_method, "POST")
        self.assertIn("zone", cfg.api_body or {})

    def test_env_placeholder_resolution_and_missing_detection(self) -> None:
        with patch.dict(os.environ, {"BRIGHTDATA_API_TOKEN": "tok123", "BRIGHTDATA_ZONE": ""}, clear=False):
            resolved, missing = resolve_env_placeholders(
                {"auth": "Bearer ${BRIGHTDATA_API_TOKEN}", "zone": "${BRIGHTDATA_ZONE}"}
            )
        self.assertEqual(resolved["auth"], "Bearer tok123")
        self.assertEqual(missing, ["BRIGHTDATA_ZONE"])

    def test_fetcher_uses_fallback_when_brightdata_env_missing(self) -> None:
        cfg = TrendsPipelineConfig.model_validate_json(
            Path("configs/google_trends_pipeline.json").read_text(encoding="utf-8")
        )
        with patch.dict(os.environ, {"BRIGHTDATA_API_TOKEN": "", "BRIGHTDATA_ZONE": ""}, clear=False):
            data = asyncio.run(fetch_trends_data(cfg))
        self.assertEqual(data["query"], "AI")
        self.assertIn("timeseries", data)

    def test_fetcher_posts_json_body_when_credentials_set(self) -> None:
        cfg = TrendsPipelineConfig.model_validate_json(
            Path("configs/google_trends_pipeline.json").read_text(encoding="utf-8")
        )
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '{"timeseries": [{"time": "2026-11-27", "value": [99]}]}'
        mock_resp.json.return_value = {"timeseries": [{"time": "2026-11-27", "value": [99]}]}

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value.request = AsyncMock(return_value=mock_resp)

        with patch.dict(os.environ, {"BRIGHTDATA_API_TOKEN": "tok_abc", "BRIGHTDATA_ZONE": "serp_zone"}):
            with patch("trends_pipeline.fetcher.httpx.AsyncClient", return_value=mock_client):
                data = asyncio.run(fetch_trends_data(cfg))

        self.assertEqual(data["timeseries"][0]["value"], [99])
        call_kwargs = mock_client.__aenter__.return_value.request.call_args
        self.assertEqual(call_kwargs.args[0], "POST")
        self.assertEqual(call_kwargs.kwargs["json"]["zone"], "serp_zone")


if __name__ == "__main__":
    unittest.main()
