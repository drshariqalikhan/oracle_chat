#!/usr/bin/env python3
"""
Entrypoint for running any config-driven API -> Ollama -> Telegram pipeline.

Usage:
    python3 -m pipeline.runner configs/quote_pipeline.json
    python3 -m pipeline.runner configs/quote_pipeline.json --once
"""
import argparse
import asyncio
import logging
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from pydantic import ValidationError

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

from pipeline.fetcher import fetch_api_data
from pipeline.llm_processor import process_with_ollama
from pipeline.models import PipelineConfig
from pipeline.notifier import format_notification, send_telegram_notification
from pipeline.storage import init_db, save_record
from scripts.json_2_masterSchema import build_master_schema

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


async def run_cycle(cfg: PipelineConfig, master_schema: dict[str, Any]) -> None:
    logger.info(f"[{cfg.pipeline_name}] Calling API: {cfg.api_url}")
    api_data = await fetch_api_data(cfg)

    logger.info(f"[{cfg.pipeline_name}] Processing with local Ollama...")
    llm_out = await process_with_ollama(cfg, master_schema, api_data)

    message_text = format_notification(cfg, api_data, llm_out)
    msg_id = await send_telegram_notification(message_text)
    if msg_id:
        save_record(
            table_name=cfg.db_table_name,
            message_id=msg_id,
            pipeline_name=cfg.pipeline_name,
            raw_api_data=api_data,
            llm_output=llm_out,
            feedback_instructions=cfg.feedback_prompt_instructions,
        )
        logger.info(f"[{cfg.pipeline_name}] Sent & saved to '{cfg.db_table_name}' (message_id={msg_id}).")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Modular config-driven API -> Ollama -> Telegram worker.")
    parser.add_argument("config_file", help="Path to pipeline JSON config file.")
    parser.add_argument("--once", action="store_true", help="Run a single cycle and exit.")
    args = parser.parse_args()

    cfg_path = Path(args.config_file)
    if not cfg_path.is_file():
        logger.error(f"Config file not found: {cfg_path}")
        sys.exit(1)

    try:
        cfg = PipelineConfig.model_validate_json(cfg_path.read_text(encoding="utf-8"))
    except ValidationError as exc:
        logger.error(f"Invalid config file:\n{exc}")
        sys.exit(1)

    init_db(cfg.db_table_name)
    master_schema = build_master_schema(
        cfg.example_api_responses,
        title=f"{cfg.pipeline_name} Input Schema",
    )
    logger.info(
        f"Loaded pipeline '{cfg.pipeline_name}' | Table='{cfg.db_table_name}' | "
        f"Interval={cfg.trigger_interval_seconds}s"
    )

    while True:
        try:
            await run_cycle(cfg, master_schema)
        except Exception:
            logger.exception(f"[{cfg.pipeline_name}] Error during pipeline cycle")

        if args.once:
            break
        await asyncio.sleep(cfg.trigger_interval_seconds)


if __name__ == "__main__":
    asyncio.run(main())
