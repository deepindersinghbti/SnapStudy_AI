from pathlib import Path
import logging
import re
import time

from pdf2image import convert_from_path
from PIL import Image
import pytesseract

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
logger = logging.getLogger(__name__)
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}


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


def _extract_from_image(path: Path) -> str:
    with Image.open(path) as image:
        return pytesseract.image_to_string(image)


def _extract_from_pdf(path: Path) -> str:
    pages = convert_from_path(path)
    text_chunks: list[str] = []
    for page in pages:
        text_chunks.append(pytesseract.image_to_string(page))
    return "\n\n".join(text_chunks)


def extract_text_from_file(file_path: str) -> str:
    start_time = time.perf_counter()
    path = Path(file_path)
    ext = path.suffix.lower()

    try:
        if ext in IMAGE_EXTENSIONS:
            raw_text = _extract_from_image(path)
        elif ext == ".pdf":
            raw_text = _extract_from_pdf(path)
        else:
            raise ValueError("Unsupported file type for OCR")

        cleaned_text = clean_extracted_text(raw_text)
        duration = time.perf_counter() - start_time
        logger.info(
            "OCR extraction completed for %s in %.2fs (chars=%d)",
            path.name,
            duration,
            len(cleaned_text),
        )
        return cleaned_text
    except Exception as exc:
        duration = time.perf_counter() - start_time
        logger.exception(
            "OCR extraction failed for %s after %.2fs",
            path.name,
            duration,
        )
        raise RuntimeError("OCR extraction failed") from exc
