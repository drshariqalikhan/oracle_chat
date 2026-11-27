#!/usr/bin/env python3
import asyncio
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv

import sqlite3
BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / 'data' / 'quote_feedback.db'
load_dotenv(BASE_DIR / ".env")

import re as _re
_m = _re.search(r"(\d+:[A-Za-z0-9_-]+)", os.getenv("TELEGRAM_BOT_TOKEN", ""))
TELEGRAM_BOT_TOKEN = _m.group(1) if _m else ""
OWNER_TELEGRAM_ID = os.getenv("OWNER_TELEGRAM_ID", "").strip()
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma4:e4b-it-qat").strip()
OLLAMA_API_URL = os.getenv("OLLAMA_API_URL", "http://localhost:11434/api/chat").strip()

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


def save_sent_quote(message_id: int, quote: dict, summary: str) -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(DB_PATH)) as conn:
        conn.execute('CREATE TABLE IF NOT EXISTS sent_quotes (message_id INTEGER PRIMARY KEY, quote TEXT, author TEXT, summary TEXT)')
        conn.execute('INSERT OR REPLACE INTO sent_quotes VALUES (?, ?, ?, ?)', (message_id, quote['quote'], quote['author'], summary))


async def get_random_quote() -> dict:
    import random
    headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
    async with httpx.AsyncClient(timeout=15.0, headers=headers, follow_redirects=True) as client:
        # 1. Try Stoic Quotes API
        try:
            r = await client.get("https://api.kanye.rest/")
            if r.status_code == 200 and r.text.strip().startswith("{"):
                d = r.json()
                logger.info(f"json res : {d}")
                if d.get("quote"):
                    return {"quote": d["quote"], "author": "ye!"}
        except Exception:
            logger.info(f"fail api call : {Exception}")
            pass

    # 3. Built-in fallback if datacenter IP is blocked by external APIs
    fallbacks = [
        {"quote": "Simplicity is prerequisite for reliability.", "author": "Edsger W. Dijkstra"},
        {"quote": "We suffer more often in imagination than in reality.", "author": "Seneca"},
        {"quote": "The impediment to action advances action. What stands in the way becomes the way.", "author": "Marcus Aurelius"},
        {"quote": "First, solve the problem. Then, write the code.", "author": "John Johnson"},
    ]
    return random.choice(fallbacks)


async def summarize_with_ollama(quote_data: dict) -> str:
    timestamp = datetime.now(timezone.utc).isoformat()
    quote_data["timestamp"] = timestamp

    prompt = (
        f"You are a helpful assistant. Here is a JSON object with a quote:\n{quote_data}\n\n"
        "Instructions:\n"
        "1. Summarize what this quote really means in exactly 100 words.\n"
        f"2. End your summary with: 'Summary generated at: {timestamp}'\n"
        "3. Keep the output clean and concise."
    )

    payload = {
        "model": OLLAMA_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "think": False,
        "options": {"num_ctx": 4096},
    }

    async with httpx.AsyncClient(timeout=300.0) as client:
        resp = await client.post(OLLAMA_API_URL, json=payload)
        resp.raise_for_status()
        return resp.json().get("message", {}).get("content", "Error summarizing.").strip()



async def notify_user(quote: dict, summary: str) -> int | None:
    text = (
        f"✨ Daily Quote Update\n\n\"{quote['quote']}\"\n— {quote['author']}\n\n"
        f"🤖 Local Ollama Summary:\n{summary}\n\n"
        f"💬 Reply to this message with why you liked or disliked this summary!"
    )
    url = 'https://api.' + 'telegram.org/bot' + TELEGRAM_BOT_TOKEN + '/sendMessage'
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(url, json={'chat_id': OWNER_TELEGRAM_ID, 'text': text})
        resp.raise_for_status()
        return resp.json().get('result', {}).get('message_id')


async def main() -> None:
    logger.info(f"Quote worker started using local Ollama model: {OLLAMA_MODEL}")
    while True:
        try:
            logger.info("Fetching new quote...")
            quote = await get_random_quote()
            summary = await summarize_with_ollama(quote)
            msg_id = await notify_user(quote, summary)
            if msg_id:
                save_sent_quote(msg_id, quote, summary)
            logger.info("Notification sent. Sleeping for 10 minutes.")
        except Exception:
            logger.exception("Error during quote cycle")
        await asyncio.sleep(600)


if __name__ == "__main__":
    asyncio.run(main())
