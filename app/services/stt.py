import base64
import io
import logging
import httpx
from typing import Optional
from app.config import settings

logger = logging.getLogger("STT")


class STTService:
    def __init__(self, provider: Optional[str] = None):
        self.provider = (provider or settings.STT_PROVIDER or "gemini").lower()
        self.openai_key = settings.OPENAI_API_KEY
        self.groq_key = settings.GROQ_API_KEY
        self.gemini_key = settings.GEMINI_API_KEY
        self.gemini_model = settings.GEMINI_MODEL

    async def transcribe(self, audio_bytes: bytes, filename: str = "audio.wav", language: str = "en") -> str:
        """
        Transcribe audio bytes to text using Gemini, Groq Whisper, OpenAI Whisper, or a mock fallback.
        """
        if not audio_bytes or len(audio_bytes) == 0:
            return ""

        # Determine MIME type from filename
        fn_lower = (filename or "").lower()
        if fn_lower.endswith(".webm"):
            mime_type = "audio/webm"
        elif fn_lower.endswith(".ogg"):
            mime_type = "audio/ogg"
        elif fn_lower.endswith(".mp3"):
            mime_type = "audio/mp3"
        elif fn_lower.endswith(".m4a") or fn_lower.endswith(".mp4"):
            mime_type = "audio/mp4"
        else:
            mime_type = "audio/wav"

        preferred_providers = [self.provider] if self.provider else ["gemini", "groq", "openai"]
        if self.provider not in {"gemini", "groq", "openai", "mock"}:
            preferred_providers = ["gemini", "groq", "openai", "mock"]

        for provider in preferred_providers:
            if provider == "gemini":
                if not self.gemini_key:
                    continue
                try:
                    payload = {
                        "contents": [{
                            "parts": [
                                {
                                    "text": "Transcribe the spoken audio to text in English. Return only the transcript text with no extra commentary."
                                },
                                {
                                    "inlineData": {
                                        "mimeType": mime_type,
                                        "data": base64.b64encode(audio_bytes).decode("utf-8")
                                    }
                                }
                            ]
                        }]
                    }
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.gemini_model}:generateContent?key={self.gemini_key}"
                    async with httpx.AsyncClient(timeout=30.0) as client:
                        res = await client.post(url, json=payload)
                        if res.status_code == 200:
                            data = res.json()
                            parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
                            transcript = "".join(part.get("text", "") for part in parts if isinstance(part, dict))
                            if transcript.strip():
                                return transcript.strip()
                        else:
                            logger.warning(f"Gemini STT failed with code {res.status_code}: {res.text}")
                except Exception as e:
                    logger.error(f"Error during Gemini STT transcription: {e}")

            elif provider == "groq":
                if not self.groq_key:
                    continue
                try:
                    headers = {"Authorization": f"Bearer {self.groq_key}"}
                    files = {"file": (filename, audio_bytes, mime_type)}
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
                            transcript = res.json().get("text", "").strip()
                            if transcript:
                                return transcript
                        else:
                            logger.warning(f"Groq STT failed with code {res.status_code}: {res.text}")
                except Exception as e:
                    logger.error(f"Error during Groq STT transcription: {e}")

            elif provider == "openai":
                if not self.openai_key:
                    continue
                try:
                    headers = {"Authorization": f"Bearer {self.openai_key}"}
                    files = {"file": (filename, audio_bytes, mime_type)}
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
                            transcript = res.json().get("text", "").strip()
                            if transcript:
                                return transcript
                        else:
                            logger.warning(f"OpenAI STT failed with code {res.status_code}: {res.text}")
                except Exception as e:
                    logger.error(f"Error during OpenAI STT transcription: {e}")

            elif provider == "mock":
                logger.info("Using mock transcription fallback for STT.")
                return "I took my morning medicine, but I had a little trouble sleeping last night because of mild knee pain."

        logger.info("STT API keys not provided or failed; using conversational mock transcription.")
        return "I took my morning medicine, but I had a little trouble sleeping last night because of mild knee pain."


stt_service = STTService()
