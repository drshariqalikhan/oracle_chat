import json
import logging
import os
import re
from typing import Any

import httpx

from pipeline.models import LLMProcessedOutput, PipelineConfig

logger = logging.getLogger(__name__)

_m = re.search(r"(\d+:[A-Za-z0-9_-]+)", os.getenv("TELEGRAM_BOT_TOKEN", ""))
TELEGRAM_BOT_TOKEN = _m.group(1) if _m else ""
OWNER_TELEGRAM_ID = os.getenv("OWNER_TELEGRAM_ID", "").strip().strip("'\"")


def format_notification(cfg: PipelineConfig, api_data: dict[str, Any], llm_out: LLMProcessedOutput) -> str:
    context: dict[str, Any] = {
        "pipeline_name": cfg.pipeline_name,
        "headline": llm_out.headline,
        "summary": llm_out.summary,
        "category": llm_out.sentiment_or_category,
        "generated_at": llm_out.generated_at,
        "raw_json": json.dumps(api_data, ensure_ascii=False),
    }
    for k, v in api_data.items():
        if isinstance(v, (str, int, float, bool)):
            context.setdefault(k, v)

    try:
        rendered = cfg.notify_template.format(**context)
    except KeyError as exc:
        logger.warning(f"Template key {exc} missing in API response; using default format.")
        rendered = f"✨ {cfg.pipeline_name}\n\n{llm_out.headline}\n\n{llm_out.summary}"

    return f"{rendered}\n\n💬 Reply to this message with why you liked or disliked this output!"


async def send_telegram_notification(message_text: str) -> int | None:
    if not TELEGRAM_BOT_TOKEN or not OWNER_TELEGRAM_ID:
        raise RuntimeError("TELEGRAM_BOT_TOKEN or OWNER_TELEGRAM_ID missing in .env")

    url = "https://api." + "telegram.org/bot" + TELEGRAM_BOT_TOKEN + "/sendMessage"
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(url, json={"chat_id": OWNER_TELEGRAM_ID, "text": message_text[:4000]})
        resp.raise_for_status()
        return resp.json().get("result", {}).get("message_id")
