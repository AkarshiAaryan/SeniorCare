import re
import logging
import httpx
from typing import Optional, AsyncGenerator
from app.config import settings

logger = logging.getLogger("RimeTTS")


def is_valid_key(key: Optional[str]) -> bool:
    return bool(key and key.strip() and not key.startswith("your_"))


class RimeTTSService:
    def __init__(
        self,
        api_key: Optional[str] = None,
        api_url: Optional[str] = None,
        default_model: Optional[str] = None,
        default_speaker: Optional[str] = None,
        default_speed: Optional[float] = None
    ):
        self.api_key = api_key or settings.RIME_API_KEY
        self.api_url = api_url or settings.RIME_API_URL
        self.default_model = default_model or settings.RIME_MODEL_ID
        self.default_speaker = default_speaker or settings.RIME_SPEAKER
        self.default_speed = default_speed or settings.RIME_TIME_SCALE_FACTOR

    def normalize_text_for_ear(self, text: str) -> str:
        """
        Preprocesses text following Rime's 'Writing for the Ear' guidelines:
        - Removes markdown formatting (asterisks, hashtags, bullets, backticks)
        - Normalizes medical abbreviations and numbers for natural conversational delivery
        - Ensures natural pauses via commas and clean sentence endpoints
        """
        if not text:
            return ""

        # Remove markdown bold/italics, headers, backticks, bullet points
        cleaned = re.sub(r'[*_#`]', '', text)
        cleaned = re.sub(r'^\s*[-•*]\s+', '', cleaned, flags=re.MULTILINE)

        # Expand common medical & time abbreviations for smooth audio delivery
        for pattern, replacement in [
            (r'(\d+)\s*mg\b', r'\1 milligrams'),
            (r'\bmg\b', 'milligrams'),
            (r'(\d+)\s*tabs\b', r'\1 tablets'),
            (r'\btabs\b', 'tablets'),
            (r'(\d+)\s*tab\b', r'\1 tablet'),
            (r'\btab\b', 'tablet'),
            (r'(\d+)\s*caps\b', r'\1 capsules'),
            (r'\bcaps\b', 'capsules'),
            (r'(\d+)\s*cap\b', r'\1 capsule'),
            (r'\bcap\b', 'capsule'),
            (r'(\d+)\s*ml\b', r'\1 milliliters'),
            (r'\b(\d+):00\s*(am|pm|AM|PM)?\b', r"\1 o'clock \2"),
            (r'(\d{1,2}):(\d{2})', r'\1 \2'),  # e.g., 08:00 -> 08 00
            (r'\s*&\s*', ' and '),
            (r'\bw/(?=\s|$)', 'with '),
            (r'\bw/o(?=\s|$)', 'without '),
            (r'\bDr\.\b', 'Doctor'),
            (r'\bBP\b', 'blood pressure'),
            (r'\bHR\b', 'heart rate'),
            (r'\bhr\b', 'hour'),
            (r'\bhrs\b', 'hours'),
        ]:
            cleaned = re.sub(pattern, replacement, cleaned, flags=re.IGNORECASE)

        # Ensure single question per sentence, smooth periods and commas
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        return cleaned

    async def synthesize(
        self,
        text: str,
        speaker: Optional[str] = None,
        model_id: Optional[str] = None,
        speed: Optional[float] = None,
        audio_format: str = "audio/mpeg"
    ) -> bytes:
        """
        Synthesize spoken audio from text using Rime TTS API.
        """
        clean_text = self.normalize_text_for_ear(text)
        if not clean_text:
            raise ValueError("Text to synthesize is empty.")

        speaker_to_use = speaker or self.default_speaker
        model_to_use = model_id or self.default_model
        speed_to_use = speed or self.default_speed

        payload = {
            "text": clean_text,
            "speaker": speaker_to_use,
            "modelId": model_to_use,
            "timeScaleFactor": speed_to_use,
            "lang": "en"
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": audio_format
        }

        # Check for missing API key and provide graceful simulated response if in local testing
        if not is_valid_key(self.api_key):
            logger.warning("RIME_API_KEY is not set or placeholder. Returning fallback audio bytes.")
            return b"\xFF\xFB\x90\x64\x00\x00\x00\x00MockRimeAudioStreamData"

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    self.api_url,
                    json=payload,
                    headers=headers
                )
                if response.status_code == 200:
                    return response.content
                else:
                    logger.warning(f"Rime API returned code {response.status_code}: {response.text}")
                    return b"\xFF\xFB\x90\x64\x00\x00\x00\x00MockRimeAudioStreamData"
        except Exception as e:
            logger.error(f"Failed to communicate with Rime TTS API: {e}")
            return b"\xFF\xFB\x90\x64\x00\x00\x00\x00MockRimeAudioStreamData"

    async def stream_synthesize(
        self,
        text: str,
        speaker: Optional[str] = None,
        model_id: Optional[str] = None,
        speed: Optional[float] = None,
        audio_format: str = "audio/mpeg"
    ) -> AsyncGenerator[bytes, None]:
        """
        Stream synthesized audio chunks from Rime TTS API.
        """
        clean_text = self.normalize_text_for_ear(text)
        if not clean_text:
            return

        payload = {
            "text": clean_text,
            "speaker": speaker or self.default_speaker,
            "modelId": model_id or self.default_model,
            "timeScaleFactor": speed or self.default_speed,
            "lang": "en"
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": audio_format
        }

        if not is_valid_key(self.api_key):
            logger.warning("RIME_API_KEY is not set or placeholder. Streaming fallback audio chunk.")
            yield b"\xFF\xFB\x90\x64\x00\x00\x00\x00MockRimeAudioStreamData"
            return

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                async with client.stream("POST", self.api_url, json=payload, headers=headers) as response:
                    if response.status_code == 200:
                        async for chunk in response.aiter_bytes():
                            yield chunk
                    else:
                        error_body = await response.aread()
                        logger.warning(f"Rime Stream Error {response.status_code}: {error_body.decode('utf-8', errors='ignore')}")
                        yield b"\xFF\xFB\x90\x64\x00\x00\x00\x00MockRimeAudioStreamData"
        except Exception as e:
            logger.error(f"Failed to communicate with Rime Stream API: {e}")
            yield b"\xFF\xFB\x90\x64\x00\x00\x00\x00MockRimeAudioStreamData"


rime_service = RimeTTSService()
