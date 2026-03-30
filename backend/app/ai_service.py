import logging
import time

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

SYSTEM_PROMPT = (
    "You are a helpful tutor. Explain the following content in a clear, simple, "
    "and structured way. Simplify difficult ideas, keep it concise but helpful, "
    "and write for student-level understanding."
)

FALLBACK_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash-lite",
]


def generate_explanation(text: str) -> str:
    start_time = time.perf_counter()
    cleaned_text = text.strip()

    if not cleaned_text:
        logger.info("AI explanation skipped: input text is empty")
        return ""

    try:
        try:
            from google import genai
            from google.genai import types
        except Exception:
            logger.exception("Gemini SDK import failed. Install dependency: google-genai")
            return ""

        if not settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY is not configured")

        client = genai.Client(api_key=settings.gemini_api_key)
        candidates = [settings.ai_model] + [m for m in FALLBACK_MODELS if m != settings.ai_model]
        last_error: Exception | None = None

        for model_name in candidates:
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=cleaned_text,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT,
                        temperature=0.2,
                    ),
                )

                explanation = (response.text or "").strip()
                duration = time.perf_counter() - start_time
                logger.info(
                    "AI explanation generated in %.2fs (input_chars=%d, output_chars=%d, model=%s)",
                    duration,
                    len(cleaned_text),
                    len(explanation),
                    model_name,
                )
                return explanation
            except Exception as exc:
                last_error = exc
                logger.warning("AI model failed, trying fallback model: %s", model_name)

        if last_error:
            raise last_error
        raise RuntimeError("No AI model candidates available")
    except Exception:
        duration = time.perf_counter() - start_time
        logger.exception(
            "AI explanation generation failed after %.2fs (input_chars=%d, output_chars=0)",
            duration,
            len(cleaned_text),
        )
        return ""
