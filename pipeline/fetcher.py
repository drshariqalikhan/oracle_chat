import logging
import random
from typing import Any

import httpx

from pipeline.models import PipelineConfig

logger = logging.getLogger(__name__)


async def fetch_api_data(cfg: PipelineConfig) -> dict[str, Any]:
    headers = {
        "User-Agent": "Mozilla/5.0 (ORACLE_CHAT PipelineWorker/1.0)",
        "Accept": "application/json",
        **cfg.api_headers,
    }
    async with httpx.AsyncClient(timeout=20.0, headers=headers, follow_redirects=True) as client:
        try:
            resp = await client.request(cfg.api_method.upper(), cfg.api_url)
            if resp.status_code == 200 and resp.text.strip().startswith("{"):
                return resp.json()
            logger.warning(f"API returned HTTP {resp.status_code}: {resp.text[:120]}")
        except Exception as exc:
            logger.warning(f"API call failed ({exc})")

    if cfg.fallback_responses:
        logger.info("Using fallback response from config.")
        return random.choice(cfg.fallback_responses)

    raise RuntimeError(f"Failed to fetch JSON from {cfg.api_url} and no fallback_responses configured.")
