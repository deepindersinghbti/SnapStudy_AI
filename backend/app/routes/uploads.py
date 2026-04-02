from pathlib import Path
import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.ai_service import generate_explanation, generate_follow_up_response
from app.auth import get_current_user
from app.config import get_settings
from app.db import get_db
from app.models import Conversation, ConversationMessage, Upload, User
from app.ocr_service import (
    ExtractionErrorCode,
    ExtractionResult,
    extract_text_from_file,
)
from app.schemas import (
    FollowUpCreateRequest,
    FollowUpCreateResponse,
    FollowUpHistoryResponse,
    FollowUpMessageRead,
    UploadCreateResponse,
    UploadRead,
)
from app.utils.file_utils import (
    allowed_extension,
    allowed_mime_type,
    save_upload_file,
    validate_extension_mime_pair,
)

router = APIRouter(prefix="/uploads", tags=["uploads"])
settings = get_settings()
logger = logging.getLogger(__name__)


def _message_for_extraction_error(error_code: str | None, file_type: str) -> str:
    if error_code == ExtractionErrorCode.DEPENDENCY_MISSING:
        return (
            "Document processing dependencies are missing on the server. "
            "Please contact support and try again later."
        )
    if error_code == ExtractionErrorCode.TEXT_BELOW_THRESHOLD:
        if file_type == "pdf":
            return (
                "Some text was detected, but not enough reliable content was extracted from the PDF. "
                "Try a clearer or text-selectable PDF."
            )
        return (
            "The uploaded image contains too little readable text. "
            "Try a clearer image with higher contrast."
        )
    if error_code == ExtractionErrorCode.NO_TEXT_FOUND:
        if file_type == "pdf":
            return (
                "No readable text was found in the PDF after parser and OCR processing. "
                "Try a clearer scan or a text-selectable PDF."
            )
        return "No readable text was found in the image. Try a clearer photo."
    if error_code == ExtractionErrorCode.UNSUPPORTED_TYPE:
        return "Unsupported file type for extraction."
    if error_code == ExtractionErrorCode.PARSER_FAILED:
        return (
            "Could not parse text from the PDF. OCR fallback was attempted but did not produce usable text."
        )
    if error_code == ExtractionErrorCode.OCR_FAILED:
        return "OCR processing failed for this file. Please try another file."
    return "Could not extract readable text from this file."


def _state_from_extraction(result: ExtractionResult) -> tuple[str, str | None]:
    if not result.success:
        return "failure", None
    if result.truncated:
        note = (
            f"Processed {result.pages_processed} of {result.total_pages} pages "
            f"(page limit: {settings.pdf_max_pages})."
        )
        return "partial", note
    return "success", None


def _parse_explanation_for_state(upload: Upload) -> tuple[str, str | None]:
    explanation = (upload.explanation or "").strip()
    extracted = (upload.extracted_text or "").strip()

    if explanation.startswith("Processing note:"):
        first_line = explanation.splitlines()[0]
        return "partial", first_line.replace("Processing note:", "").strip() or None
    if not extracted:
        return "failure", explanation or "No readable text was extracted."
    return "success", None


def _extract_note_prefix(explanation: str) -> tuple[str | None, str]:
    if not explanation.startswith("Processing note:"):
        return None, explanation
    parts = explanation.split("\n\n", 1)
    note = parts[0].replace("Processing note:", "").strip()
    body = parts[1] if len(parts) == 2 else ""
    return note or None, body


def _get_owned_upload(db: Session, upload_id: int, user_id: int) -> Upload:
    upload = (
        db.query(Upload)
        .filter(Upload.id == upload_id, Upload.user_id == user_id)
        .first()
    )
    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found")
    return upload


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

    extraction = extract_text_from_file(
        saved_path,
        min_text_length=settings.min_text_length,
        max_pdf_pages=settings.pdf_max_pages,
    )
    state, state_note = _state_from_extraction(extraction)
    logger.info(
        (
            "upload_extraction file=%s user_id=%d type=%s state=%s method=%s "
            "pages_processed=%d total_pages=%d truncated=%s text_len=%d error=%s"
        ),
        Path(saved_path).name,
        current_user.id,
        file_type,
        state,
        extraction.method,
        extraction.pages_processed,
        extraction.total_pages,
        extraction.truncated,
        len(extraction.text),
        extraction.error,
    )

    if extraction.success:
        record.extracted_text = extraction.text
        ai_explanation = generate_explanation(record.extracted_text)

        if ai_explanation:
            if state == "partial" and state_note:
                record.explanation = f"Processing note: {state_note}\n\n{ai_explanation}"
            else:
                record.explanation = ai_explanation
        else:
            fallback_message = "Text extracted, but AI explanation is currently unavailable."
            if state == "partial" and state_note:
                record.explanation = f"Processing note: {state_note}\n\n{fallback_message}"
            else:
                record.explanation = fallback_message
    else:
        record.extracted_text = ""
        record.explanation = _message_for_extraction_error(
            extraction.error, file_type)

    db.add(record)
    db.commit()
    db.refresh(record)

    response_note, _ = _extract_note_prefix(record.explanation)
    if state == "failure":
        response_note = record.explanation

    return UploadCreateResponse(
        upload_id=record.id,
        file_type=record.file_type,
        processing_state=state,
        processing_note=response_note,
        extraction_method=extraction.method,
        pages_processed=extraction.pages_processed,
        total_pages=extraction.total_pages,
        truncated=extraction.truncated,
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
    response_rows: list[UploadRead] = []
    for row in records:
        state, note = _parse_explanation_for_state(row)
        _, explanation_body = _extract_note_prefix(row.explanation or "")
        response_rows.append(
            UploadRead(
                id=row.id,
                file_path=row.file_path,
                file_type=row.file_type,
                extracted_text=row.extracted_text,
                explanation=explanation_body,
                processing_state=state,
                processing_note=note,
                extraction_method=None,
                pages_processed=None,
                total_pages=None,
                truncated=(state == "partial"),
                created_at=row.created_at,
            )
        )
    return response_rows


@router.get("/{upload_id}/followups", response_model=FollowUpHistoryResponse)
def list_followups(
    upload_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FollowUpHistoryResponse:
    _get_owned_upload(db, upload_id, current_user.id)

    conversation = (
        db.query(Conversation)
        .filter(
            Conversation.upload_id == upload_id,
            Conversation.user_id == current_user.id,
        )
        .first()
    )
    if not conversation:
        return FollowUpHistoryResponse(conversation_id=None, messages=[])

    messages = (
        db.query(ConversationMessage)
        .filter(ConversationMessage.conversation_id == conversation.id)
        .order_by(ConversationMessage.created_at.asc(), ConversationMessage.id.asc())
        .all()
    )

    return FollowUpHistoryResponse(
        conversation_id=conversation.id,
        messages=[
            FollowUpMessageRead(
                id=row.id,
                question=row.user_message,
                response=row.ai_response,
                created_at=row.created_at,
            )
            for row in messages
        ],
    )


@router.post("/{upload_id}/followups", response_model=FollowUpCreateResponse)
def create_followup(
    upload_id: int,
    payload: FollowUpCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FollowUpCreateResponse:
    upload = _get_owned_upload(db, upload_id, current_user.id)

    question = payload.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    conversation = (
        db.query(Conversation)
        .filter(
            Conversation.upload_id == upload.id,
            Conversation.user_id == current_user.id,
        )
        .first()
    )
    if not conversation:
        conversation = Conversation(
            upload_id=upload.id, user_id=current_user.id)
        db.add(conversation)
        db.flush()

    prior_messages = (
        db.query(ConversationMessage)
        .filter(ConversationMessage.conversation_id == conversation.id)
        .order_by(ConversationMessage.created_at.asc(), ConversationMessage.id.asc())
        .all()
    )
    history = [
        {"question": row.user_message, "response": row.ai_response}
        for row in prior_messages
    ]

    ai_response = generate_follow_up_response(
        extracted_text=upload.extracted_text,
        explanation=upload.explanation,
        question=question,
        history=history,
    )

    message = ConversationMessage(
        conversation_id=conversation.id,
        user_message=question,
        ai_response=ai_response,
    )
    db.add(message)
    db.commit()
    db.refresh(message)

    return FollowUpCreateResponse(
        conversation_id=conversation.id,
        message_id=message.id,
        question=message.user_message,
        response=message.ai_response,
        created_at=message.created_at,
    )
