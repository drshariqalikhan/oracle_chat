#!/usr/bin/env python3
import asyncio
import logging
import os
from pathlib import Path

import httpx
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
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

TELEGRAM_API = f"https://telegram.org{TELEGRAM_BOT_TOKEN}"


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
    url = f"{TELEGRAM_API}/sendMessage"
    for i in range(0, len(text), 4000):
        chunk = text[i : i + 4000]
        async with httpx.AsyncClient(timeout=15.0) as client:
            await client.post(url, json={"chat_id": chat_id, "text": chunk})


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
