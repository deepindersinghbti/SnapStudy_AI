from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import logging
import re
import time

from PIL import Image
import pytesseract

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}


class ExtractionMethod:
    PARSER = "parser"
    OCR = "ocr"
    NONE = "none"


class ExtractionErrorCode:
    UNSUPPORTED_TYPE = "UNSUPPORTED_TYPE"
    PARSER_FAILED = "PARSER_FAILED"
    OCR_FAILED = "OCR_FAILED"
    DEPENDENCY_MISSING = "DEPENDENCY_MISSING"
    NO_TEXT_FOUND = "NO_TEXT_FOUND"
    TEXT_BELOW_THRESHOLD = "TEXT_BELOW_THRESHOLD"


@dataclass(slots=True)
class ExtractionResult:
    success: bool
    text: str
    method: str
    pages_processed: int
    total_pages: int
    truncated: bool
    error: str | None


def _configure_tesseract_cmd() -> None:
    configured_path = (settings.tesseract_cmd or "").strip()
    if not configured_path:
        return

    if Path(configured_path).exists():
        pytesseract.pytesseract.tesseract_cmd = configured_path
        logger.info(
            "OCR configured with explicit tesseract path: %s", configured_path)
    else:
        logger.warning(
            "Configured tesseract path does not exist, falling back to system PATH: %s",
            configured_path,
        )


def clean_extracted_text(text: str) -> str:
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    non_empty_lines: list[str] = []
    previous_blank = False

    for line in lines:
        if line == "":
            if not previous_blank and non_empty_lines:
                non_empty_lines.append("")
            previous_blank = True
            continue
        non_empty_lines.append(line)
        previous_blank = False

    return "\n".join(non_empty_lines).strip()


def _dependency_error(message: str) -> str:
    text = message.lower()
    if "tesseract" in text:
        return ExtractionErrorCode.DEPENDENCY_MISSING
    return ""


def _extract_from_image(path: Path) -> str:
    with Image.open(path) as image:
        return pytesseract.image_to_string(image)


def _parse_pdf_text(path: Path, pages_limit: int) -> tuple[str, int, int, bool, str | None]:
    try:
        import fitz  # type: ignore
    except Exception:
        logger.exception("PyMuPDF import failed")
        return "", 0, 0, False, ExtractionErrorCode.DEPENDENCY_MISSING

    try:
        with fitz.open(path) as doc:
            total_pages = doc.page_count
            pages_processed = min(total_pages, pages_limit)
            truncated = total_pages > pages_limit
            text_chunks: list[str] = []

            for page_index in range(pages_processed):
                text_chunks.append(doc[page_index].get_text("text"))

            return "\n\n".join(text_chunks), pages_processed, total_pages, truncated, None
    except Exception as exc:
        logger.exception("PDF parser extraction failed for %s", path.name)
        dependency_error = _dependency_error(str(exc))
        return "", 0, 0, False, dependency_error or ExtractionErrorCode.PARSER_FAILED


def _ocr_pdf_text(path: Path, pages_limit: int) -> tuple[str, int, int, bool, str | None]:
    try:
        import fitz  # type: ignore

        with fitz.open(path) as doc:
            total_pages = doc.page_count
            pages_processed = min(total_pages, pages_limit)
            truncated = total_pages > pages_limit
            text_chunks: list[str] = []

            for idx in range(pages_processed):
                page = doc.load_page(idx)
                pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                if pixmap.n == 1:
                    mode = "L"
                elif pixmap.n < 4:
                    mode = "RGB"
                else:
                    mode = "RGBA"
                image = Image.frombytes(
                    mode, [pixmap.width, pixmap.height], pixmap.samples)
                page_text = pytesseract.image_to_string(image)
                text_chunks.append(page_text)
                logger.info(
                    "pdf_ocr_page file=%s page=%d chars=%d",
                    path.name,
                    idx + 1,
                    len(clean_extracted_text(page_text)),
                )

        return "\n\n".join(text_chunks), pages_processed, total_pages, truncated, None
    except Exception as exc:
        logger.exception("PDF OCR extraction failed for %s", path.name)
        dependency_error = _dependency_error(str(exc))
        return "", 0, 0, False, dependency_error or ExtractionErrorCode.OCR_FAILED


def _result_from_text(
    *,
    text: str,
    method: str,
    pages_processed: int,
    total_pages: int,
    truncated: bool,
    min_text_length: int,
) -> ExtractionResult:
    cleaned_text = clean_extracted_text(text)
    text_len = len(cleaned_text)

    if text_len == 0:
        return ExtractionResult(
            success=False,
            text="",
            method=ExtractionMethod.NONE,
            pages_processed=pages_processed,
            total_pages=total_pages,
            truncated=truncated,
            error=ExtractionErrorCode.NO_TEXT_FOUND,
        )

    if text_len < min_text_length:
        return ExtractionResult(
            success=False,
            text=cleaned_text,
            method=method,
            pages_processed=pages_processed,
            total_pages=total_pages,
            truncated=truncated,
            error=ExtractionErrorCode.TEXT_BELOW_THRESHOLD,
        )

    return ExtractionResult(
        success=True,
        text=cleaned_text,
        method=method,
        pages_processed=pages_processed,
        total_pages=total_pages,
        truncated=truncated,
        error=None,
    )


def extract_text_from_file(
    file_path: str,
    *,
    min_text_length: int | None = None,
    max_pdf_pages: int | None = None,
) -> ExtractionResult:
    _configure_tesseract_cmd()

    start_time = time.perf_counter()
    path = Path(file_path)
    ext = path.suffix.lower()
    threshold = min_text_length or settings.min_text_length
    page_limit = max_pdf_pages or settings.pdf_max_pages

    result: ExtractionResult
    fallback_triggered = False

    if ext in IMAGE_EXTENSIONS:
        try:
            raw_text = _extract_from_image(path)
            result = _result_from_text(
                text=raw_text,
                method=ExtractionMethod.OCR,
                pages_processed=1,
                total_pages=1,
                truncated=False,
                min_text_length=threshold,
            )
            if not result.success and result.error == ExtractionErrorCode.TEXT_BELOW_THRESHOLD:
                result = ExtractionResult(
                    success=False,
                    text="",
                    method=ExtractionMethod.OCR,
                    pages_processed=1,
                    total_pages=1,
                    truncated=False,
                    error=ExtractionErrorCode.TEXT_BELOW_THRESHOLD,
                )
        except Exception as exc:
            logger.exception("Image OCR extraction failed for %s", path.name)
            dependency_error = _dependency_error(str(exc))
            result = ExtractionResult(
                success=False,
                text="",
                method=ExtractionMethod.NONE,
                pages_processed=0,
                total_pages=0,
                truncated=False,
                error=dependency_error or ExtractionErrorCode.OCR_FAILED,
            )
    elif ext == ".pdf":
        parser_text, parser_pages, parser_total, parser_truncated, parser_error = _parse_pdf_text(
            path, page_limit
        )
        parser_result = _result_from_text(
            text=parser_text,
            method=ExtractionMethod.PARSER,
            pages_processed=parser_pages,
            total_pages=parser_total,
            truncated=parser_truncated,
            min_text_length=threshold,
        )

        should_fallback = (not parser_result.success) and (
            parser_error is None
            or parser_error in {
                ExtractionErrorCode.PARSER_FAILED,
                ExtractionErrorCode.DEPENDENCY_MISSING,
                ExtractionErrorCode.NO_TEXT_FOUND,
                ExtractionErrorCode.TEXT_BELOW_THRESHOLD,
            }
        )

        if should_fallback:
            fallback_triggered = True
            ocr_text, ocr_pages, ocr_total, ocr_truncated, ocr_error = _ocr_pdf_text(
                path, page_limit)
            ocr_result = _result_from_text(
                text=ocr_text,
                method=ExtractionMethod.OCR,
                pages_processed=ocr_pages,
                total_pages=ocr_total or parser_total,
                truncated=ocr_truncated or parser_truncated,
                min_text_length=threshold,
            )
            if ocr_result.success:
                result = ocr_result
            else:
                final_error = ocr_error or ocr_result.error or parser_error
                result = ExtractionResult(
                    success=False,
                    text="",
                    method=ExtractionMethod.OCR if (
                        ocr_pages or ocr_total) else ExtractionMethod.NONE,
                    pages_processed=ocr_pages or parser_pages,
                    total_pages=ocr_total or parser_total,
                    truncated=ocr_truncated or parser_truncated,
                    error=final_error or ExtractionErrorCode.NO_TEXT_FOUND,
                )
        elif parser_result.success:
            result = parser_result
        else:
            result = ExtractionResult(
                success=False,
                text="",
                method=ExtractionMethod.NONE,
                pages_processed=parser_pages,
                total_pages=parser_total,
                truncated=parser_truncated,
                error=parser_error or parser_result.error or ExtractionErrorCode.PARSER_FAILED,
            )
    else:
        result = ExtractionResult(
            success=False,
            text="",
            method=ExtractionMethod.NONE,
            pages_processed=0,
            total_pages=0,
            truncated=False,
            error=ExtractionErrorCode.UNSUPPORTED_TYPE,
        )

    duration = time.perf_counter() - start_time
    logger.info(
        (
            "extraction_result file=%s ext=%s success=%s method=%s fallback=%s "
            "pages_processed=%d total_pages=%d truncated=%s text_len=%d error=%s duration=%.2fs"
        ),
        path.name,
        ext,
        result.success,
        result.method,
        fallback_triggered,
        result.pages_processed,
        result.total_pages,
        result.truncated,
        len(result.text),
        result.error,
        duration,
    )
    return result
