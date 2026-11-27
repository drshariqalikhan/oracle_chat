import asyncio
import os
import sys
import logging
import httpx
from pathlib import Path
from dotenv import load_dotenv

# Path setup for repo
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
OWNER_TELEGRAM_ID = os.getenv("OWNER_TELEGRAM_ID", "").strip()
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3.5:9b").strip()
OLLAMA_API_URL = os.getenv("OLLAMA_API_URL", "http://localhost:11434/api/chat").strip()

if not TELEGRAM_BOT_TOKEN or not OWNER_TELEGRAM_ID:
    print("ERROR: TELEGRAM_BOT_TOKEN and OWNER_TELEGRAM_ID must be set in .env", file=sys.stderr)
    sys.exit(1)

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

# State storage
chat_preferences = {}

def get_pref(chat_id: str) -> dict:
    if chat_id not in chat_preferences:
        chat_preferences[chat_id] = {"provider": "ollama", "model": ""}
    return chat_preferences[chat_id]

async def get_ollama_installed_models() -> list[str]:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{OLLAMA_API_URL.rsplit('/api/', 1)[0]}/api/tags")
            if resp.status_code == 200:
                return [m["name"] for m in resp.json().get("models", [])]
    except Exception: pass
    return []

async def query_llm(provider: str, model: str, prompt: str) -> str:
    if provider == "ollama":
        url = OLLAMA_API_URL
        target_model = model
        if not target_model:
            models = await get_ollama_installed_models()
            target_model = models[0] if models else "gemma4:e4b-it-qat"

        payload = {
            "model": target_model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "think": False,
            "options": {"num_ctx": 4096}
        }
        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                response = await client.post(url, json=payload)
                data = response.json()
                return data.get("message", {}).get("content", "Empty response.")
        except Exception as exc: return f"Ollama failed: {exc}"
    
    # OpenRouter logic
    return "OpenRouter logic here..."

async def poll_telegram():
    logger.info("Bot started.")
    offset = 0
    async with httpx.AsyncClient(timeout=35.0) as client:
        while True:
            try:
                resp = await client.get(f"{TELEGRAM_API}/getUpdates?offset={offset}&timeout=30")
                for result in resp.json().get("result", []):
                    offset = result["update_id"] + 1
                    msg = result.get("message", {})
                    if str(msg.get("from", {}).get("id")) != OWNER_TELEGRAM_ID: continue
                    text = msg.get("text", "")
                    
                    # Simple handling
                    reply = await query_llm(get_pref(str(msg["chat"]["id"]))["provider"], "", text)
                    await client.post(f"{TELEGRAM_API}/sendMessage", json={"chat_id": msg["chat"]["id"], "text": reply})
            except Exception: await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(poll_telegram())
