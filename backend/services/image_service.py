import base64
import io
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile
from PIL import Image, UnidentifiedImageError

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_PIL_FORMATS = {"JPEG", "PNG", "WEBP"}
EXTENSION_TO_MIME = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}
MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 10 MB


class ImageValidationError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


@dataclass(frozen=True)
class SavedImageInfo:
    file_id: str
    original_filename: str
    url: str
    content_type: str
    size_bytes: int
    width: int
    height: int


class ImageService:
    def __init__(self, uploads_dir: Path) -> None:
        self.uploads_dir = uploads_dir
        self.uploads_dir.mkdir(parents=True, exist_ok=True)

    async def save_image(self, file: UploadFile) -> SavedImageInfo:
        original_name = (file.filename or "image").strip()
        suffix = Path(original_name).suffix.lower()

        if suffix not in ALLOWED_EXTENSIONS:
            allowed_list = ", ".join(sorted(ALLOWED_EXTENSIONS))
            raise ImageValidationError(
                f"Unsupported image extension '{suffix or 'none'}'. Allowed: {allowed_list}",
                status_code=400,
            )

        content = await file.read()
        if not content:
            raise ImageValidationError("Uploaded image file is empty.", status_code=400)

        if len(content) > MAX_IMAGE_BYTES:
            raise ImageValidationError(
                f"Image exceeds maximum allowed size of {MAX_IMAGE_BYTES // (1024 * 1024)} MB.",
                status_code=413,
            )

        try:
            with Image.open(io.BytesIO(content)) as img:
                img.verify()
            with Image.open(io.BytesIO(content)) as img:
                width, height = img.size
                pil_format = (img.format or "").upper()
        except (UnidentifiedImageError, OSError, ValueError) as exc:
            raise ImageValidationError(
                "Invalid or corrupted image file. Please upload a valid JPG, PNG, or WEBP image.",
                status_code=400,
            ) from exc

        if pil_format not in ALLOWED_PIL_FORMATS:
            raise ImageValidationError(
                f"Unsupported image format '{pil_format}'. Allowed: JPEG, PNG, WEBP.",
                status_code=400,
            )

        normalized_ext = ".jpg" if pil_format == "JPEG" else f".{pil_format.lower()}"
        saved_filename = f"{uuid4().hex}{normalized_ext}"
        destination = self.uploads_dir / saved_filename
        destination.write_bytes(content)

        content_type = file.content_type or EXTENSION_TO_MIME[normalized_ext]
        return SavedImageInfo(
            file_id=saved_filename,
            original_filename=original_name,
            url=f"/uploads/{saved_filename}",
            content_type=content_type,
            size_bytes=len(content),
            width=width,
            height=height,
        )

    def load_image_as_data_url(self, file_id: str) -> str:
        cleaned_id = file_id.strip()
        if not cleaned_id or Path(cleaned_id).name != cleaned_id:
            raise ImageValidationError("Invalid image file_id.", status_code=400)

        image_path = self.uploads_dir / cleaned_id
        if not image_path.is_file():
            raise ImageValidationError(
                f"Uploaded image '{cleaned_id}' was not found.",
                status_code=404,
            )

        suffix = image_path.suffix.lower()
        mime_type = EXTENSION_TO_MIME.get(suffix)
        if not mime_type:
            raise ImageValidationError(
                f"Unsupported image extension '{suffix}'.",
                status_code=400,
            )

        encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
        return f"data:{mime_type};base64,{encoded}"
