#!/usr/bin/env python3
import asyncio
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
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


async def get_random_quote() -> dict:
    headers = {"User-Agent": "Mozilla/5.0 (ORACLE_CHAT QuoteWorker/1.0)", "Accept": "application/json"}
    async with httpx.AsyncClient(timeout=15.0, headers=headers, follow_redirects=True) as client:
        try:
            resp = await client.get("https://dummyjson.com")
            if resp.status_code == 200 and resp.text.strip():
                return resp.json()
        except Exception as exc:
            logger.warning(f"Primary quote API failed ({exc}), trying fallback...")

        resp = await client.get("https://zenquotes.io")
        resp.raise_for_status()
        items = resp.json()
        return {"quote": items[0]["q"], "author": items[0]["a"]}


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


async def notify_user(quote: dict, summary: str) -> None:
text = f"✨ Daily Quote Update\n\n"{quote['quote']}"\n— {quote['author']}\n\n🤖 Local Ollama Summary:\n{summary}"
url = f"telegram.org{TELEGRAM_BOT_TOKEN}/sendMessage"
async with httpx.AsyncClient(timeout=15.0) as client:
resp = await client.post(url, json={"chat_id": OWNER_TELEGRAM_ID, "text": text})
resp.raise_for_status()
async def main() -> None:
logger.info(f"Quote worker started using local Ollama model: {OLLAMA_MODEL}")
while True:
try:
logger.info("Fetching new quote...")
quote = await get_random_quote()
summary = await summarize_with_ollama(quote)
await notify_user(quote, summary)
logger.info("Notification sent. Sleeping for 10 minutes.")
except Exception:
logger.exception("Error during quote cycle")
await asyncio.sleep(600)
if name == "main":
asyncio.run(main())
