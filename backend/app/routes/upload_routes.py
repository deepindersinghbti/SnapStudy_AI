from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.ai_service import generate_explanation
from app.auth import get_current_user
from app.config import get_settings
from app.db import get_db
from app.models import Upload, User
from app.ocr_service import extract_text_from_file
from app.schemas import UploadCreateResponse, UploadRead
from app.utils.file_utils import (
    allowed_extension,
    allowed_mime_type,
    save_upload_file,
    validate_extension_mime_pair,
)

router = APIRouter(prefix="/uploads", tags=["uploads"])
settings = get_settings()


@router.post("", response_model=UploadCreateResponse, status_code=status.HTTP_201_CREATED)
def upload_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UploadCreateResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename")

    if not allowed_extension(file.filename):
        raise HTTPException(status_code=400, detail="Unsupported file type")

    if not allowed_mime_type(file.content_type):
        raise HTTPException(status_code=400, detail="Unsupported MIME type")

    if not validate_extension_mime_pair(file.filename, file.content_type):
        raise HTTPException(
            status_code=400,
            detail="File extension does not match MIME type",
        )

    try:
        saved_path = save_upload_file(file, settings.max_upload_size_mb)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    ext = Path(saved_path).suffix.lower()
    file_type = "pdf" if ext == ".pdf" else "image"

    record = Upload(
        user_id=current_user.id,
        file_path=saved_path,
        file_type=file_type,
        extracted_text="",
        explanation="",
    )

    try:
        record.extracted_text = extract_text_from_file(saved_path)
    except RuntimeError:
        # Upload still succeeds, and extracted text remains empty when OCR fails.
        record.extracted_text = ""

    record.explanation = generate_explanation(record.extracted_text)

    db.add(record)
    db.commit()
    db.refresh(record)

    return UploadCreateResponse(
        upload_id=record.id,
        file_type=record.file_type,
        created_at=record.created_at,
    )


@router.get("", response_model=list[UploadRead])
def list_uploads(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[UploadRead]:
    records = (
        db.query(Upload)
        .filter(Upload.user_id == current_user.id)
        .order_by(Upload.id.desc())
        .all()
    )
    return [
        UploadRead(
            id=row.id,
            file_path=row.file_path,
            file_type=row.file_type,
            extracted_text=row.extracted_text,
            explanation=row.explanation,
            created_at=row.created_at,
        )
        for row in records
    ]
