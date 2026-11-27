#!/usr/bin/env python3
import asyncio
import os
import logging
import httpx
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
OWNER_TELEGRAM_ID = os.getenv("OWNER_TELEGRAM_ID", "").strip()
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3.5:9b").strip()
OLLAMA_API_URL = os.getenv("OLLAMA_API_URL", "http://localhost:11434/api/chat").strip()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def get_random_quote():
    async with httpx.AsyncClient() as client:
        resp = await client.get("https://dummyjson.com/quotes/random")
        return resp.json()

async def summarize_with_ollama(quote_data):
    timestamp = datetime.now(timezone.utc).isoformat()
    quote_data["timestamp"] = timestamp
    
    prompt = (
        f"You are a helpful assistant. Here is a JSON object with a quote:\n{quote_data}\n\n"
        "Instructions:\n"
        "1. Summarize what this quote really means in exactly 100 words.\n"
        "2. End your summary with: 'Summary generated at: {timestamp}'\n"
        "3. Keep the output clean and concise."
    )
    
    payload = {
        "model": OLLAMA_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "options": {"num_ctx": 4096, "think": False}
    }
    
    async with httpx.AsyncClient(timeout=300.0) as client:
        resp = await client.post(OLLAMA_API_URL, json=payload)
        return resp.json().get("message", {}).get("content", "Error summarizing.")

async def notify_user(quote, summary):
    text = f"✨ *Daily Quote Update*\n\n\"{quote['quote']}\"\n— {quote['author']}\n\n🤖 *AI Summary:*\n{summary}"
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    async with httpx.AsyncClient() as client:
        await client.post(url, json={"chat_id": OWNER_TELEGRAM_ID, "text": text, "parse_mode": "Markdown"})

async def main():
    while True:
        logger.info("Fetching new quote...")
        quote = await get_random_quote()
        summary = await summarize_with_ollama(quote)
        await notify_user(quote, summary)
        logger.info("Notification sent. Sleeping for 10 minutes.")
        await asyncio.sleep(600)

if __name__ == "__main__":
    asyncio.run(main())
