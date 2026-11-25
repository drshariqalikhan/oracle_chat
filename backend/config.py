import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


@dataclass(frozen=True)
class Settings:
    app_host: str
    app_port: int
    llm_provider: str
    model_name: str
    openrouter_api_key: str
    openrouter_base_url: str
    ollama_base_url: str


def get_settings() -> Settings:
    return Settings(
        app_host=os.getenv("APP_HOST", "0.0.0.0"),
        app_port=int(os.getenv("APP_PORT", "8080")),
        llm_provider=os.getenv("LLM_PROVIDER", "openrouter").strip().lower(),
        model_name=os.getenv("MODEL_NAME", "openrouter/free").strip(),
        openrouter_api_key=os.getenv("OPENROUTER_API_KEY", "").strip(),
        openrouter_base_url=os.getenv(
            "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
        ).strip().rstrip("/"),
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").strip().rstrip("/"),
    )
