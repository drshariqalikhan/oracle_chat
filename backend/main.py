from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.config import get_settings
from backend.routes.chat import router as chat_router
from backend.routes.health import router as health_router
from backend.routes.upload import router as upload_router

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
TEMPLATES_DIR = FRONTEND_DIR / "templates"
STATIC_DIR = FRONTEND_DIR / "static"
UPLOADS_DIR = BASE_DIR / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

get_settings()

app = FastAPI(title="ORACLE CHAT", version="0.9.0")

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")
app.include_router(health_router)
app.include_router(chat_router)
app.include_router(upload_router)


@app.get("/")
async def home() -> FileResponse:
    return FileResponse(TEMPLATES_DIR / "index.html")
