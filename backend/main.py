import asyncio
import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.config import get_settings
from backend.routes.chat import router as chat_router
from backend.routes.health import router as health_router

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
TEMPLATES_DIR = FRONTEND_DIR / "templates"
STATIC_DIR = FRONTEND_DIR / "static"

get_settings()

app = FastAPI(title="ORACLE CHAT", version="0.4.0")

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.include_router(health_router)
app.include_router(chat_router)


def _fetch_ollama_tags(base_url: str) -> dict[str, Any]:
    tags_url = f"{base_url.rstrip('/')}/api/tags"
    req = urllib.request.Request(
        tags_url,
        headers={"Accept": "application/json"},
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=5) as response:
        body = response.read().decode("utf-8")
        return json.loads(body)


@app.get("/")
async def home() -> FileResponse:
    return FileResponse(TEMPLATES_DIR / "index.html")


@app.get("/api/ollama/models")
async def discover_ollama_models(
    base_url: str = Query(default="http://localhost:11434"),
) -> dict[str, Any]:
    cleaned_url = base_url.strip().rstrip("/")
    parsed = urlparse(cleaned_url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid Ollama URL: '{base_url}'. Must start with http:// or https://",
        )

    try:
        payload = await asyncio.to_thread(_fetch_ollama_tags, cleaned_url)
    except urllib.error.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Ollama returned HTTP {exc.code} at {cleaned_url}/api/tags",
        ) from exc
    except urllib.error.URLError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Cannot reach Ollama at {cleaned_url} ({exc.reason})",
        ) from exc
    except TimeoutError as exc:
        raise HTTPException(
            status_code=504,
            detail=f"Timed out connecting to Ollama at {cleaned_url}",
        ) from exc
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Invalid JSON received from Ollama at {cleaned_url}/api/tags",
        ) from exc

    raw_models = payload.get("models", [])
    models = [
        {
            "name": item.get("name", ""),
            "size": item.get("size", 0),
            "modified_at": item.get("modified_at", ""),
        }
        for item in raw_models
        if item.get("name")
    ]

    return {
        "status": "ok",
        "base_url": cleaned_url,
        "count": len(models),
        "models": models,
    }
