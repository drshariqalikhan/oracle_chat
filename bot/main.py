#!/usr/bin/env python3
import asyncio
import os
import sys
import logging
import httpx
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
OWNER_TELEGRAM_ID = os.getenv("OWNER_TELEGRAM_ID", "").strip()
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3.5:9b").strip()
OLLAMA_API_URL = os.getenv("OLLAMA_API_URL", "http://localhost:11434/api/chat").strip()

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

async def query_ollama(prompt: str) -> str:
    logger.info(f"Querying Ollama model: {OLLAMA_MODEL} with prompt: {prompt[:50]}...")
    payload = {
        "model": OLLAMA_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "options": {"num_ctx": 4096}
    }
    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(OLLAMA_API_URL, json=payload)
            if response.status_code != 200:
                return f"Ollama error (HTTP {response.status_code}): {response.text}"
            data = response.json()
            return data.get("message", {}).get("content", "Empty response.")
    except Exception as exc:
        logger.exception("Failed to connect to Ollama")
        return f"Failed to reach local Ollama engine: {exc}"

async def send_telegram_message(chat_id: str, text: str):
    url = f"{TELEGRAM_API}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    async with httpx.AsyncClient(timeout=10.0) as client:
        await client.post(url, json=payload)

async def poll_telegram():
    logger.info("Bot polling started.")
    offset = 0
    async with httpx.AsyncClient(timeout=35.0) as client:
        while True:
            try:
                resp = await client.get(f"{TELEGRAM_API}/getUpdates?offset={offset}&timeout=30")
                if resp.status_code != 200:
                    await asyncio.sleep(5); continue
                
                for result in resp.json().get("result", []):
                    offset = result["update_id"] + 1
                    msg = result.get("message", {})
                    
                    user_id = str(msg.get("from", {}).get("id", ""))
                    chat_id = str(msg.get("chat", {}).get("id", ""))
                    text = msg.get("text", "").strip()
                    
                    if user_id != OWNER_TELEGRAM_ID:
                        logger.warning(f"Unauthorized: {user_id}")
                        continue
                    
                    if not text:
                        logger.info("Ignoring non-text message")
                        continue

                    logger.info(f"Command received: {text}")
                    await send_telegram_message(chat_id, "🧠 Processing...")
                    reply = await query_ollama(text)
                    await send_telegram_message(chat_id, reply)
            except Exception:
                logger.exception("Polling error")
                await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(poll_telegram())
