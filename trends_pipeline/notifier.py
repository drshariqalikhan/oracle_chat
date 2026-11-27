import json
import logging
import os
import re
from typing import Any

import httpx

from trends_pipeline.models import TrendsLLMOutput, TrendsPipelineConfig

logger = logging.getLogger(__name__)


def format_notification(
    cfg: TrendsPipelineConfig,
    api_data: dict[str, Any],
    llm_out: TrendsLLMOutput,
) -> str:
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
        rendered = f"📈 {cfg.pipeline_name}\n\n{llm_out.headline}\n\n{llm_out.summary}"

    return f"{rendered}\n\n💬 Reply to this message with why you liked or disliked this output!"


async def send_telegram_notification(message_text: str) -> int | None:
    m = re.search(r"(\d+:[A-Za-z0-9_-]+)", os.getenv("TELEGRAM_BOT_TOKEN", ""))
    tg_token = m.group(1) if m else ""
    owner_id = os.getenv("OWNER_TELEGRAM_ID", "").strip().strip("'\"")

    if not tg_token or not owner_id:
        raise RuntimeError("TELEGRAM_BOT_TOKEN or OWNER_TELEGRAM_ID missing in .env")

    url = f"https://api.telegram.org/bot{tg_token}/sendMessage"
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(url, json={"chat_id": owner_id, "text": message_text[:4000]})
        resp.raise_for_status()
        return resp.json().get("result", {}).get("message_id")
