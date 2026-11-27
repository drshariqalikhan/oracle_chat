#!/usr/bin/env python3
import asyncio
import logging
import os
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

ACTIVE_PROVIDER = os.getenv("BOT_PROVIDER", "openrouter").strip().lower()
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma4:e4b-it-qat").strip()
OLLAMA_API_URL = os.getenv("OLLAMA_API_URL", "http://localhost:11434/api/chat").strip()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openrouter/free").strip()
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai").strip().rstrip("/")

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

import re as _re
_tok = _re.search(r"(\d+:[A-Za-z0-9_-]+)", os.getenv("TELEGRAM_BOT_TOKEN", ""))
TELEGRAM_API = "https://api.telegram.org/bot" + TELEGRAM_BOT_TOKEN


async def query_ollama(prompt: str) -> str:
    logger.info(f"Querying Ollama ({OLLAMA_MODEL})...")
    payload = {
        "model": OLLAMA_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "think": False,
        "options": {"num_ctx": 4096},
    }
    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(OLLAMA_API_URL, json=payload)
            if response.status_code != 200:
                return f"Ollama error (HTTP {response.status_code}): {response.text}"
            data = response.json()
            return data.get("message", {}).get("content", "Empty response.").strip()
    except Exception as exc:
        logger.exception("Failed to connect to Ollama")
        return f"Failed to reach local Ollama engine: {exc}"


async def query_openrouter(prompt: str) -> str:
    if not OPENROUTER_API_KEY:
        return "OpenRouter API key is not configured in .env."
    logger.info(f"Querying OpenRouter ({OPENROUTER_MODEL})...")
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com",
        "X-Title": "ORACLE CHAT Bot",
    }
    payload = {
        "model": OPENROUTER_MODEL,
        "messages": [{"role": "user", "content": prompt}],
    }
    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            response = await client.post(f"{OPENROUTER_BASE_URL}/chat/completions", headers=headers, json=payload)
            if response.status_code != 200:
                return f"OpenRouter error (HTTP {response.status_code}): {response.text}"
            data = response.json()
            choices = data.get("choices") or []
            if not choices:
                return "OpenRouter returned no choices."
            return choices[0].get("message", {}).get("content", "Empty response.").strip()
    except Exception as exc:
        logger.exception("Failed to connect to OpenRouter")
        return f"Failed to reach OpenRouter: {exc}"


async def send_telegram_message(chat_id: str, text: str) -> None:
    url = "https://api.telegram.org/bot" + TELEGRAM_BOT_TOKEN + "/sendMessage"
    for i in range(0, len(text), 4000):
        chunk = text[i : i + 4000]
        async with httpx.AsyncClient(timeout=15.0) as client:
            await client.post(url, json={"chat_id": chat_id, "text": chunk})


def lookup_sent_quote(reply_id: int | None) -> dict | None:
    if not reply_id or not DB_PATH.is_file():
        return None
    with sqlite3.connect(str(DB_PATH)) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute('SELECT quote, author, summary FROM sent_quotes WHERE message_id = ?', (reply_id,)).fetchone()
        return dict(row) if row else None


async def handle_quote_feedback(chat_id: str, user_opinion: str, quote_record: dict) -> None:
    await send_telegram_message(chat_id, '🧠 Reviewing your feedback with local Ollama...')
    prompt = (
        f"Quote: \"{quote_record['quote']}\" — {quote_record['author']}\n"
        f"Your Summary: {quote_record['summary']}\n"
        f"User Opinion: \"{user_opinion}\"\n\n"
        'If the user likes or approves of your summary, warmly thank them and briefly acknowledge why. '
        'If they dislike or critique it, sincerely apologize and acknowledge their specific reason. Keep it under 80 words.'
    )
    reply = await query_ollama(prompt)
    await send_telegram_message(chat_id, reply)


async def handle_command(chat_id: str, text: str) -> bool:
    global ACTIVE_PROVIDER, OLLAMA_MODEL, OPENROUTER_MODEL

    parts = text.split(maxsplit=1)
    cmd = parts[0].lower()
    arg = parts[1].strip() if len(parts) > 1 else ""

    if cmd == "/status":
        current_model = OLLAMA_MODEL if ACTIVE_PROVIDER == "ollama" else OPENROUTER_MODEL
        status_msg = (
            f"ORACLE CHAT Bot Online\n"
            f"Conversation Provider: {ACTIVE_PROVIDER}\n"
            f"Model: {current_model}\n"
            f"Quote Background Task: local ollama ({OLLAMA_MODEL})"
        )
        await send_telegram_message(chat_id, status_msg)
        return True

    if cmd == "/provider":
        if arg.lower() not in ("ollama", "openrouter"):
            await send_telegram_message(chat_id, "Usage: /provider ollama OR /provider openrouter")
            return True
        ACTIVE_PROVIDER = arg.lower()
        current_model = OLLAMA_MODEL if ACTIVE_PROVIDER == "ollama" else OPENROUTER_MODEL
        await send_telegram_message(chat_id, f"Switched conversation provider to: {ACTIVE_PROVIDER} ({current_model})")
        return True

    if cmd == "/model":
        if not arg:
            await send_telegram_message(chat_id, "Usage: /model <model_name>")
            return True
        if ACTIVE_PROVIDER == "ollama":
            OLLAMA_MODEL = arg
        else:
            OPENROUTER_MODEL = arg
        await send_telegram_message(chat_id, f"Active {ACTIVE_PROVIDER} model set to: {arg}")
        return True

    return False


async def poll_telegram() -> None:
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN is empty in .env!")
        return
    logger.info(f"Bot polling started. Conversation Provider={ACTIVE_PROVIDER}, Model={OPENROUTER_MODEL}")
    offset = 0
    async with httpx.AsyncClient(timeout=35.0) as client:
        while True:
            try:
                resp = await client.get(f"{TELEGRAM_API}/getUpdates?offset={offset}&timeout=30")
                if resp.status_code != 200:
                    await asyncio.sleep(5)
                    continue

                for result in resp.json().get("result", []):
                    offset = result["update_id"] + 1
                    msg = result.get("message", {})

                    user_id = str(msg.get("from", {}).get("id", ""))
                    chat_id = str(msg.get("chat", {}).get("id", ""))
                    text = msg.get("text", "").strip()

                    if user_id != OWNER_TELEGRAM_ID:
                        logger.warning(f"Unauthorized user ID: {user_id}")
                        continue

                    if not text:
                        continue

                    replied_id = (msg.get('reply_to_message') or {}).get('message_id')
                    quote_record = lookup_sent_quote(replied_id)
                    if quote_record:
                        logger.info(f'Quote feedback received for message_id={replied_id}')
                        await handle_quote_feedback(chat_id, text, quote_record)
                        continue

                    logger.info(f"Message received: {text[:60]}")
                    if text.startswith("/") and await handle_command(chat_id, text):
                        continue

                    await send_telegram_message(chat_id, "Processing...")
                    if ACTIVE_PROVIDER == "openrouter":
                        reply = await query_openrouter(text)
                    else:
                        reply = await query_ollama(text)
                    await send_telegram_message(chat_id, reply)
            except Exception:
                logger.exception("Polling error")
                await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(poll_telegram())
