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

FOLLOW_UP_SYSTEM_PROMPT = (
    "You are a helpful tutor handling follow-up questions about previously explained study notes. "
    "Answer clearly and directly, stay grounded in the provided context, and admit uncertainty "
    "if the context is insufficient. Keep responses practical for student learning."
)


def _generate_with_fallback(*, content: str, system_prompt: str) -> str:
    try:
        from google import genai
        from google.genai import types
    except Exception:
        logger.exception(
            "Gemini SDK import failed. Install dependency: google-genai")
        return ""

    if not settings.gemini_api_key:
        raise ValueError("GEMINI_API_KEY is not configured")

    client = genai.Client(api_key=settings.gemini_api_key)
    candidates = [settings.ai_model] + \
        [m for m in FALLBACK_MODELS if m != settings.ai_model]
    last_error: Exception | None = None

    for model_name in candidates:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=content,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=0.2,
                ),
            )
            return (response.text or "").strip()
        except Exception as exc:
            last_error = exc
            logger.warning(
                "AI model failed, trying fallback model: %s", model_name)

    if last_error:
        raise last_error
    raise RuntimeError("No AI model candidates available")


def generate_explanation(text: str) -> str:
    start_time = time.perf_counter()
    cleaned_text = text.strip()

    if not cleaned_text:
        logger.info("AI explanation skipped: input text is empty")
        return ""

    try:
        explanation = _generate_with_fallback(
            content=cleaned_text, system_prompt=SYSTEM_PROMPT)
        duration = time.perf_counter() - start_time
        logger.info(
            "AI explanation generated in %.2fs (input_chars=%d, output_chars=%d)",
            duration,
            len(cleaned_text),
            len(explanation),
        )
        return explanation
    except Exception:
        duration = time.perf_counter() - start_time
        logger.exception(
            "AI explanation generation failed after %.2fs (input_chars=%d, output_chars=0)",
            duration,
            len(cleaned_text),
        )
        return ""


def generate_follow_up_response(
    *,
    extracted_text: str,
    explanation: str,
    question: str,
    history: list[dict[str, str]] | None = None,
) -> str:
    start_time = time.perf_counter()
    cleaned_question = question.strip()
    if not cleaned_question:
        logger.info("Follow-up generation skipped: question is empty")
        return ""

    try:
        history = history or []
        max_turns = 20
        turns = history[-max_turns:]

        history_lines: list[str] = []
        for turn in turns:
            user_msg = (turn.get("question") or "").strip()
            ai_msg = (turn.get("response") or "").strip()
            if user_msg:
                history_lines.append(f"User: {user_msg}")
            if ai_msg:
                history_lines.append(f"Assistant: {ai_msg}")

        history_block = "\n".join(history_lines) if history_lines else "(none)"

        content = (
            "Original extracted text:\n"
            f"{(extracted_text or '').strip() or '(empty)'}\n\n"
            "Original explanation:\n"
            f"{(explanation or '').strip() or '(empty)'}\n\n"
            "Conversation so far:\n"
            f"{history_block}\n\n"
            "New follow-up question:\n"
            f"{cleaned_question}"
        )

        response = _generate_with_fallback(
            content=content, system_prompt=FOLLOW_UP_SYSTEM_PROMPT)
        duration = time.perf_counter() - start_time
        logger.info(
            "AI follow-up generated in %.2fs (question_chars=%d, output_chars=%d, turns=%d)",
            duration,
            len(cleaned_question),
            len(response),
            len(turns),
        )
        return response
    except Exception:
        duration = time.perf_counter() - start_time
        logger.exception(
            "AI follow-up generation failed after %.2fs (question_chars=%d, output_chars=0)",
            duration,
            len(cleaned_question),
        )
        return ""
