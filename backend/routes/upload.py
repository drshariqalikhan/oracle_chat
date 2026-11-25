from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from backend.models import ImageUploadResponse
from backend.services.image_service import ImageService, ImageValidationError

router = APIRouter(tags=["upload"])

UPLOADS_DIR = Path(__file__).resolve().parent.parent.parent / "uploads"
image_service = ImageService(uploads_dir=UPLOADS_DIR)


@router.post("/upload/image", response_model=ImageUploadResponse)
async def upload_image(file: UploadFile = File(...)) -> ImageUploadResponse:
    try:
        saved = await image_service.save_image(file)
    except ImageValidationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    return ImageUploadResponse(
        status="ok",
        file_id=saved.file_id,
        original_filename=saved.original_filename,
        url=saved.url,
        content_type=saved.content_type,
        size_bytes=saved.size_bytes,
        width=saved.width,
        height=saved.height,
    )
