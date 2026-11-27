import logging
import os
import random
import re
from typing import Any

import httpx

from trends_pipeline.models import TrendsPipelineConfig

logger = logging.getLogger(__name__)

ENV_VAR_PATTERN = re.compile(r"\$\{([A-Z0-9_]+)\}")


def resolve_env_placeholders(value: Any) -> tuple[Any, list[str]]:
    missing: list[str] = []

    if isinstance(value, str):
        def _replace(match: re.Match[str]) -> str:
            var_name = match.group(1)
            env_val = os.getenv(var_name, "").strip()
            if not env_val:
                missing.append(var_name)
            return env_val

        return ENV_VAR_PATTERN.sub(_replace, value), missing

    if isinstance(value, dict):
        resolved_dict: dict[str, Any] = {}
        for k, v in value.items():
            rv, m = resolve_env_placeholders(v)
            resolved_dict[k] = rv
            missing.extend(m)
        return resolved_dict, missing

    if isinstance(value, list):
        resolved_list: list[Any] = []
        for item in value:
            ri, m = resolve_env_placeholders(item)
            resolved_list.append(ri)
            missing.extend(m)
        return resolved_list, missing

    return value, missing


async def fetch_trends_data(cfg: TrendsPipelineConfig) -> dict[str, Any]:
    resolved_headers, missing_hdr = resolve_env_placeholders(cfg.api_headers)
    resolved_body, missing_body = resolve_env_placeholders(cfg.api_body)
    missing_vars = sorted(set(missing_hdr + missing_body))

    if missing_vars:
        logger.warning(
            "Missing environment variable(s) %s for '%s'; using fallback data.",
            ", ".join(missing_vars),
            cfg.pipeline_name,
        )
        if cfg.fallback_responses:
            return random.choice(cfg.fallback_responses)
        raise RuntimeError(f"Missing required environment variable(s): {', '.join(missing_vars)}")

    headers = {
        "User-Agent": "Mozilla/5.0 (ORACLE_CHAT TrendsPipeline/1.0)",
        "Accept": "application/json",
        **resolved_headers,
    }
    method = cfg.api_method.upper()

    async with httpx.AsyncClient(timeout=30.0, headers=headers, follow_redirects=True) as client:
        try:
            if resolved_body is not None and method != "GET":
                resp = await client.request(method, cfg.api_url, json=resolved_body)
            else:
                resp = await client.request(method, cfg.api_url)

            body_text = resp.text.strip()
            if resp.status_code == 200 and (body_text.startswith("{") or body_text.startswith("[")):
                parsed = resp.json()
                return parsed if isinstance(parsed, dict) else {"items": parsed}
            logger.warning(f"Trends API returned HTTP {resp.status_code}: {resp.text[:160]}")
        except Exception as exc:
            logger.warning(f"Trends API call failed ({exc})")

    if cfg.fallback_responses:
        logger.info("Using fallback response from config.")
        return random.choice(cfg.fallback_responses)

    raise RuntimeError(f"Failed to fetch JSON from {cfg.api_url} and no fallback_responses configured.")
