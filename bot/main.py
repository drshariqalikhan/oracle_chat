import asyncio
import os
import sys
import logging
import httpx
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent if 'Path' in globals() else None
# Fallback base dir calculation
import pathlib
BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
OWNER_TELEGRAM_ID = os.getenv("OWNER_TELEGRAM_ID", "").strip()
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3.5:9b").strip()
OLLAMA_API_URL = os.getenv("OLLAMA_API_URL", "http://localhost:11434/api/chat").strip()

if not TELEGRAM_BOT_TOKEN or not OWNER_TELEGRAM_ID:
    print("ERROR: TELEGRAM_BOT_TOKEN and OWNER_TELEGRAM_ID must be set in .env", file=sys.stderr)
    sys.exit(1)

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

async def query_ollama(prompt: str) -> str:
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
            return data.get("message", {}).get("content", "Empty response from model.")
    except Exception as exc:
        logger.exception("Failed to connect to Ollama")
        return f"Failed to reach local Ollama engine: {exc}"

async def send_telegram_message(chat_id: str, text: str):
    url = f"{TELEGRAM_API}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            await client.post(url, json=payload)
        except Exception:
            logger.exception("Failed to send Telegram message")

async def poll_telegram():
    logger.info(f"Starting custom Telegram polling bot (Model: {OLLAMA_MODEL})...")
    offset = 0
    async with httpx.AsyncClient(timeout=35.0) as client:
        while True:
            try:
                url = f"{TELEGRAM_API}/getUpdates?offset={offset}&timeout=30"
                response = await client.get(url)
                if response.status_code != 200:
                    await asyncio.sleep(5)
                    continue
                
                data = response.json()
                for result in data.get("result", []):
                    offset = result["update_id"] + 1
                    message = result.get("message")
                    if not message:
                        continue
                    
                    user = message.get("from", {})
                    user_id = str(user.get("id", ""))
                    chat_id = str(message.get("chat", {}).get("id", ""))
                    text = message.get("text", "").strip()

                    # Security check: Ignore anyone who is not you!
                    if user_id != OWNER_TELEGRAM_ID:
                        logger.warning(f"Ignored unauthorized message from user_id: {user_id}")
                        await send_telegram_message(chat_id, "Unauthorized. This bot is private.")
                        continue

                    if not text:
                        continue

                    logger.info(f"Received owner command: {text}")
                    
                    if text.lower() == "/status":
                        await send_telegram_message(chat_id, f"🟢 Custom Oracle Bot active. Model: {OLLAMA_MODEL}")
                        continue

                    await send_telegram_message(chat_id, "🧠 Thinking...")
                    reply = await query_ollama(text)
                    await send_telegram_message(chat_id, reply)

            except (httpx.ReadTimeout, httpx.ConnectTimeout):
                continue
            except Exception:
                logger.exception("Error in polling loop")
                await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(poll_telegram())
