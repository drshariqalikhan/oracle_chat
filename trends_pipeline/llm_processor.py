import json
import os
import re
from datetime import datetime, timezone
from typing import Any

import httpx

from trends_pipeline.models import TrendsLLMOutput, TrendsPipelineConfig


def _extract_json_block(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        return cleaned[start : end + 1]
    return cleaned


async def process_with_ollama(
    cfg: TrendsPipelineConfig,
    master_schema: dict[str, Any],
    live_api_data: dict[str, Any],
) -> TrendsLLMOutput:
    default_model = os.getenv("OLLAMA_MODEL", "gemma4:e4b-it-qat").strip().strip("'\"")
    ollama_url = os.getenv("OLLAMA_API_URL", "http://localhost:11434/api/chat").strip().strip("'\"")
    model = (cfg.ollama_model or default_model).strip()
    timestamp = datetime.now(timezone.utc).isoformat()
    output_schema = TrendsLLMOutput.model_json_schema()

    system_prompt = (
        "You are a precise data-processing engine. You will be given:\n"
        "1. The Master JSON Schema describing the expected API input structure.\n"
        "2. The live JSON payload returned by the API.\n"
        "3. The required Pydantic JSON Schema for your output.\n\n"
        "CRITICAL: Respond ONLY with a valid JSON object matching the required output schema."
    )

    user_prompt = (
        f"TASK INSTRUCTIONS:\n{cfg.llm_prompt}\n\n"
        f"CURRENT UTC TIMESTAMP: {timestamp}\n\n"
        f"EXPECTED INPUT API MASTER SCHEMA:\n{json.dumps(master_schema, indent=2)}\n\n"
        f"LIVE API JSON PAYLOAD:\n{json.dumps(live_api_data, indent=2)}\n\n"
        f"REQUIRED OUTPUT PYDANTIC JSON SCHEMA:\n{json.dumps(output_schema, indent=2)}"
    )

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "format": output_schema,
        "stream": False,
        "think": False,
        "options": {"num_ctx": 4096},
    }

    async with httpx.AsyncClient(timeout=300.0) as client:
        resp = await client.post(ollama_url, json=payload)
        resp.raise_for_status()
        raw_content = resp.json().get("message", {}).get("content", "").strip()

    parsed = json.loads(_extract_json_block(raw_content))
    if not parsed.get("generated_at"):
        parsed["generated_at"] = timestamp
    return TrendsLLMOutput.model_validate(parsed)
