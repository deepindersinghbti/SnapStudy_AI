from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from app.config import get_settings

settings = get_settings()

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".pdf"}
ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "application/pdf",
}
EXTENSION_TO_MIME = {
    ".jpg": {"image/jpeg", "image/jpg"},
    ".jpeg": {"image/jpeg", "image/jpg"},
    ".png": {"image/png"},
    ".pdf": {"application/pdf"},
}


def ensure_upload_dir() -> Path:
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    return upload_dir


def allowed_extension(filename: str) -> bool:
    ext = Path(filename).suffix.lower()
    return ext in ALLOWED_EXTENSIONS


def allowed_mime_type(content_type: str | None) -> bool:
    if not content_type:
        return False
    return content_type.lower() in ALLOWED_MIME_TYPES


def validate_extension_mime_pair(filename: str, content_type: str | None) -> bool:
    ext = Path(filename).suffix.lower()
    if ext not in EXTENSION_TO_MIME:
        return False
    if not content_type:
        return False
    return content_type.lower() in EXTENSION_TO_MIME[ext]


def save_upload_file(file: UploadFile, max_upload_size_mb: int) -> str:
    upload_dir = ensure_upload_dir()
    ext = Path(file.filename).suffix.lower()
    safe_name = f"{uuid4().hex}{ext}"
    target = upload_dir / safe_name
    max_bytes = max_upload_size_mb * 1024 * 1024
    total_bytes = 0

    try:
        with target.open("wb") as buffer:
            while True:
                chunk = file.file.read(1024 * 1024)
                if not chunk:
                    break
                total_bytes += len(chunk)
                if total_bytes > max_bytes:
                    raise ValueError(
                        f"File exceeds maximum size of {max_upload_size_mb} MB"
                    )
                buffer.write(chunk)
    except Exception:
        if target.exists():
            target.unlink(missing_ok=True)
        raise
    finally:
        file.file.close()

    return str(target.as_posix())
