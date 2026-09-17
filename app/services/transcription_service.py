import asyncio
import logging
from typing import Optional

from google import genai
from google.genai import types as genai_types

from app.core.config import settings
from app.infrastructure.providers.gemini import is_gemini_dependency_error

logger = logging.getLogger(__name__)


def _transcribe_sync(
    audio_bytes: bytes, mime_type: str, user_language: Optional[str] = None
) -> str:
    lang_hint = (
        f" The farmer's preferred language is {user_language}." if user_language else ""
    )
    prompt = (
        f"You are an agronomic speech-to-text assistant.{lang_hint} "
        "Transcribe this spoken farmer voice note verbatim in the language spoken (e.g., Telugu, Hindi, Kannada, Tamil, or English). "
        "Provide the exact transcription in the native script. "
        "If spoken in a regional language other than English, provide the native transcription, followed by an English translation on a new line starting with 'English: '. "
        "If it is in English, provide just the English text. "
        "Do not include any conversational preamble, pleasantries, or explanations."
    )
    with genai.Client() as client:
        response = client.models.generate_content(
            model=settings.GEMINI_CHAT_MODEL,
            contents=[
                genai_types.Part.from_bytes(
                    data=audio_bytes,
                    mime_type=mime_type or "audio/mp4",
                ),
                prompt,
            ],
        )
        return (response.text or "").strip()


async def transcribe_audio(
    audio_bytes: bytes,
    mime_type: str,
    user_language: Optional[str] = None,
) -> str:
    """
    Asynchronously transcribes audio recording bytes using Gemini.
    """
    if not audio_bytes:
        return ""

    try:
        return await asyncio.to_thread(
            _transcribe_sync,
            audio_bytes=audio_bytes,
            mime_type=mime_type,
            user_language=user_language,
        )
    except Exception as exc:
        if is_gemini_dependency_error(exc):
            logger.warning("Gemini transcription failed with dependency error: %s", exc)
        else:
            logger.error("Failed to transcribe audio note: %s", exc)
        return ""
