"""Shared upload handling for prescriptions and lab reports (validation, text extraction, storage)."""
import uuid
from io import BytesIO
from pathlib import Path

from fastapi import HTTPException, UploadFile
from PyPDF2 import PdfReader

from .config import MAX_UPLOAD_BYTES, UPLOAD_DIR

IMAGE_EXT = (".jpg", ".jpeg", ".png", ".heic", ".webp", ".bmp", ".tif", ".tiff")


def read_upload(file: UploadFile) -> tuple[str, bytes]:
    """Validate a PDF/TXT upload. Photos and scans need OCR, which is not available offline, so they are rejected clearly."""
    name = (file.filename or "upload").replace("\\", "/").split("/")[-1][:100]
    low = name.lower()
    if low.endswith(IMAGE_EXT):
        raise HTTPException(415, "Photos and scanned images need OCR, which is not available. Upload a text-based PDF or a TXT file, or enter the details manually.")
    if not low.endswith((".pdf", ".txt")):
        raise HTTPException(415, "Only PDF or TXT files are supported")
    data = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "File is larger than 5 MB")
    if low.endswith(".pdf") and not data.startswith(b"%PDF"):
        raise HTTPException(415, "File content is not a valid PDF")
    return name, data


def extract_text(data: bytes, filename: str) -> str:
    if filename.lower().endswith(".pdf"):
        try:
            reader = PdfReader(BytesIO(data))
            text = "\n".join((p.extract_text() or "") for p in reader.pages)[:20000]
        except Exception:
            raise HTTPException(422, "Could not read this PDF. Try a text-based (not scanned) PDF.")
        if not text.strip():
            raise HTTPException(422, "No readable text found. This looks like a scanned PDF, which needs OCR. Upload a text-based PDF or enter the details manually.")
        return text
    return data.decode("utf-8", errors="ignore")[:20000]


def store_file(user_id: int, name: str, data: bytes) -> Path:
    folder = UPLOAD_DIR / str(user_id)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{uuid.uuid4().hex}{'.pdf' if name.lower().endswith('.pdf') else '.txt'}"
    path.write_bytes(data)
    return path


def remove_file(user_id: int, stored_path: str) -> None:
    """Delete a stored upload, but only if it lives inside this user's folder."""
    try:
        target = (UPLOAD_DIR / str(user_id) / Path(stored_path.replace("\\", "/")).name)
        target.unlink(missing_ok=True)
    except OSError:
        pass
