from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile
from pypdf import PdfReader

ALLOWED_DOC_EXTENSIONS = {".pdf", ".txt"}
MAX_DOCUMENT_BYTES = 15 * 1024 * 1024  # 15 MB
MAX_EXTRACTED_CHARS = 20000


class FileValidationError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


@dataclass(frozen=True)
class SavedDocumentInfo:
    file_id: str
    original_filename: str
    file_type: str
    size_bytes: int
    page_count: int
    char_count: int
    truncated: bool
    extracted_text: str


class FileService:
    def __init__(self, uploads_dir: Path) -> None:
        self.uploads_dir = uploads_dir
        self.uploads_dir.mkdir(parents=True, exist_ok=True)

    async def save_document(self, file: UploadFile) -> SavedDocumentInfo:
        original_name = (file.filename or "document").strip()
        suffix = Path(original_name).suffix.lower()

        if suffix not in ALLOWED_DOC_EXTENSIONS:
            allowed_list = ", ".join(sorted(ALLOWED_DOC_EXTENSIONS))
            raise FileValidationError(
                f"Unsupported document extension '{suffix or 'none'}'. Allowed: {allowed_list}",
                status_code=400,
            )

        content = await file.read()
        if not content:
            raise FileValidationError("Uploaded document file is empty.", status_code=400)

        if len(content) > MAX_DOCUMENT_BYTES:
            raise FileValidationError(
                f"Document exceeds maximum allowed size of {MAX_DOCUMENT_BYTES // (1024 * 1024)} MB.",
                status_code=413,
            )

        saved_filename = f"{uuid4().hex}{suffix}"
        destination = self.uploads_dir / saved_filename
        destination.write_bytes(content)

        try:
            extracted_text, page_count = self._extract_from_path(destination, suffix)
        except FileValidationError:
            destination.unlink(missing_ok=True)
            raise

        truncated = False
        if len(extracted_text) > MAX_EXTRACTED_CHARS:
            extracted_text = (
                extracted_text[:MAX_EXTRACTED_CHARS].rstrip()
                + f"\n\n[Note: Document text truncated at {MAX_EXTRACTED_CHARS:,} characters.]"
            )
            truncated = True

        return SavedDocumentInfo(
            file_id=saved_filename,
            original_filename=original_name,
            file_type=suffix.lstrip("."),
            size_bytes=len(content),
            page_count=page_count,
            char_count=len(extracted_text),
            truncated=truncated,
            extracted_text=extracted_text,
        )

    def extract_text_by_id(self, file_id: str) -> tuple[str, int, bool]:
        cleaned_id = file_id.strip()
        if not cleaned_id or Path(cleaned_id).name != cleaned_id:
            raise FileValidationError("Invalid document file_id.", status_code=400)

        doc_path = self.uploads_dir / cleaned_id
        if not doc_path.is_file():
            raise FileValidationError(
                f"Uploaded document '{cleaned_id}' was not found.",
                status_code=404,
            )

        suffix = doc_path.suffix.lower()
        if suffix not in ALLOWED_DOC_EXTENSIONS:
            raise FileValidationError(
                f"Unsupported document extension '{suffix}'.",
                status_code=400,
            )

        text, page_count = self._extract_from_path(doc_path, suffix)
        truncated = False
        if len(text) > MAX_EXTRACTED_CHARS:
            text = (
                text[:MAX_EXTRACTED_CHARS].rstrip()
                + f"\n\n[Note: Document text truncated at {MAX_EXTRACTED_CHARS:,} characters.]"
            )
            truncated = True

        return text, page_count, truncated

    @staticmethod
    def _extract_from_path(file_path: Path, suffix: str) -> tuple[str, int]:
        if suffix == ".txt":
            raw_bytes = file_path.read_bytes()
            text = ""
            for encoding in ("utf-8", "utf-8-sig", "latin-1"):
                try:
                    text = raw_bytes.decode(encoding)
                    break
                except UnicodeDecodeError:
                    continue
            cleaned = text.strip()
            if not cleaned:
                raise FileValidationError("Text file contains no readable text.", status_code=400)
            return cleaned, 1

        try:
            reader = PdfReader(str(file_path))
        except Exception as exc:
            raise FileValidationError(
                f"Failed to read PDF file: {exc}",
                status_code=400,
            ) from exc

        pages_text: list[str] = []
        for idx, page in enumerate(reader.pages, start=1):
            page_content = (page.extract_text() or "").strip()
            if page_content:
                pages_text.append(f"[Page {idx}]\n{page_content}")

        combined = "\n\n".join(pages_text).strip()
        if not combined:
            raise FileValidationError(
                "No extractable text found in this PDF (it may be a scanned/image-only PDF).",
                status_code=400,
            )

        return combined, len(reader.pages)
