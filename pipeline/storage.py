import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pipeline.models import LLMProcessedOutput

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "quote_feedback.db"


def sanitize_table_name(name: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_]", "_", name.strip())
    return f"tbl_{cleaned}" if (not cleaned or cleaned.isdigit()) else cleaned


def init_db(table_name: str) -> None:
    safe_table = sanitize_table_name(table_name)
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(DB_PATH)) as conn:
        conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {safe_table} (
                message_id INTEGER PRIMARY KEY,
                pipeline_name TEXT NOT NULL,
                raw_api_json TEXT NOT NULL,
                llm_output_json TEXT NOT NULL,
                summary_text TEXT NOT NULL,
                feedback_instructions TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS active_message_routes (
                message_id INTEGER PRIMARY KEY,
                table_name TEXT NOT NULL,
                pipeline_name TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )


def save_record(
    table_name: str,
    message_id: int,
    pipeline_name: str,
    raw_api_data: dict[str, Any],
    llm_output: LLMProcessedOutput,
    feedback_instructions: str,
) -> None:
    safe_table = sanitize_table_name(table_name)
    now_iso = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(str(DB_PATH)) as conn:
        conn.execute(
            f"""
            INSERT OR REPLACE INTO {safe_table}
            (message_id, pipeline_name, raw_api_json, llm_output_json, summary_text, feedback_instructions, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                message_id,
                pipeline_name,
                json.dumps(raw_api_data, ensure_ascii=False),
                llm_output.model_dump_json(),
                llm_output.summary,
                feedback_instructions,
                now_iso,
            ),
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO active_message_routes (message_id, table_name, pipeline_name, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (message_id, safe_table, pipeline_name, now_iso),
        )
