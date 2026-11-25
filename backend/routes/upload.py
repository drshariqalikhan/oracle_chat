from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from backend.models import DocumentUploadResponse, ImageUploadResponse
from backend.services.file_service import FileService, FileValidationError
from backend.services.image_service import ImageService, ImageValidationError

router = APIRouter(tags=["upload"])

UPLOADS_DIR = Path(__file__).resolve().parent.parent.parent / "uploads"
image_service = ImageService(uploads_dir=UPLOADS_DIR)
file_service = FileService(uploads_dir=UPLOADS_DIR)


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


@router.post("/upload/document", response_model=DocumentUploadResponse)
async def upload_document(file: UploadFile = File(...)) -> DocumentUploadResponse:
    try:
        saved = await file_service.save_document(file)
    except FileValidationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    preview_text = saved.extracted_text[:200].replace("\n", " ").strip()
    if len(saved.extracted_text) > 200:
        preview_text += "..."

    return DocumentUploadResponse(
        status="ok",
        file_id=saved.file_id,
        original_filename=saved.original_filename,
        file_type=saved.file_type,
        size_bytes=saved.size_bytes,
        page_count=saved.page_count,
        char_count=saved.char_count,
        truncated=saved.truncated,
        preview=preview_text,
    )
