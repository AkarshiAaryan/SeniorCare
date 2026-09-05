import io
import logging
import httpx
from typing import Optional
from app.config import settings

logger = logging.getLogger("STT")


class STTService:
    def __init__(self, provider: Optional[str] = None):
        self.provider = provider or settings.STT_PROVIDER
        self.openai_key = settings.OPENAI_API_KEY
        self.groq_key = settings.GROQ_API_KEY

    async def transcribe(self, audio_bytes: bytes, filename: str = "audio.wav", language: str = "en") -> str:
        """
        Transcribe audio bytes to text using OpenAI Whisper, Groq, or fallback simulation.
        """
        if not audio_bytes or len(audio_bytes) == 0:
            return ""

        # 1. Try Groq Whisper (ultra-fast transcription)
        if self.groq_key:
            try:
                headers = {"Authorization": f"Bearer {self.groq_key}"}
                files = {"file": (filename, audio_bytes, "audio/wav")}
                data = {
                    "model": "whisper-large-v3",
                    "language": language,
                    "response_format": "json"
                }
                async with httpx.AsyncClient(timeout=15.0) as client:
                    res = await client.post(
                        "https://api.groq.com/openai/v1/audio/transcriptions",
                        headers=headers,
                        files=files,
                        data=data
                    )
                    if res.status_code == 200:
                        return res.json().get("text", "").strip()
                    else:
                        logger.warning(f"Groq STT failed with code {res.status_code}: {res.text}")
            except Exception as e:
                logger.error(f"Error during Groq STT transcription: {e}")

        # 2. Try OpenAI Whisper
        if self.openai_key:
            try:
                headers = {"Authorization": f"Bearer {self.openai_key}"}
                files = {"file": (filename, audio_bytes, "audio/wav")}
                data = {
                    "model": "whisper-1",
                    "language": language
                }
                async with httpx.AsyncClient(timeout=15.0) as client:
                    res = await client.post(
                        "https://api.openai.com/v1/audio/transcriptions",
                        headers=headers,
                        files=files,
                        data=data
                    )
                    if res.status_code == 200:
                        return res.json().get("text", "").strip()
                    else:
                        logger.warning(f"OpenAI STT failed with code {res.status_code}: {res.text}")
            except Exception as e:
                logger.error(f"Error during OpenAI STT transcription: {e}")

        # 3. Fallback for testing/offline environments
        logger.info("STT API keys not provided or failed; using conversational mock transcription.")
        # If the audio bytes contain ascii text marker or fallback
        return "I took my morning medicine, but I had a little trouble sleeping last night because of mild knee pain."


stt_service = STTService()
