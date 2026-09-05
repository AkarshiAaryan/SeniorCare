import re
import logging
import httpx
from typing import Optional, AsyncGenerator
from app.config import settings

logger = logging.getLogger("RimeTTS")


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
            (r'\b(\d+):00\s*(am|pm|AM|PM)?\b', r"\1 o'clock \2"),
            (r'\b(\d+):(\d{2})\b', r'\1 \2'),
            (r'\s*&\s*', ' and '),
            (r'\bw/(?=\s|$)', 'with '),
            (r'\bw/o(?=\s|$)', 'without '),
            (r'\bBP\b', 'blood pressure'),
            (r'\bHR\b', 'heart rate'),
            (r'\bDr\.\b', 'Doctor'),
        ]:
            cleaned = re.sub(pattern, replacement, cleaned)

        # Collapse multiple spaces and trim
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
        if not self.api_key:
            logger.warning("RIME_API_KEY is not set. Generating mock audio bytes for testing.")
            # Return valid mock MP3 header bytes for graceful offline development / testing
            return b"\xFF\xFB\x90\x64\x00\x00\x00\x00MockRimeAudioStreamData"

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                response = await client.post(
                    self.api_url,
                    json=payload,
                    headers=headers
                )
                if response.status_code != 200:
                    logger.error(f"Rime API Error {response.status_code}: {response.text}")
                    response.raise_for_status()
                return response.content
            except Exception as e:
                logger.error(f"Failed to communicate with Rime TTS API: {e}")
                raise

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

        if not self.api_key:
            logger.warning("RIME_API_KEY is not set. Streaming mock audio chunk.")
            yield b"\xFF\xFB\x90\x64\x00\x00\x00\x00MockRimeAudioStreamData"
            return

        async with httpx.AsyncClient(timeout=20.0) as client:
            async with client.stream("POST", self.api_url, json=payload, headers=headers) as response:
                if response.status_code != 200:
                    error_body = await response.aread()
                    logger.error(f"Rime Stream Error {response.status_code}: {error_body.decode('utf-8', errors='ignore')}")
                    response.raise_for_status()
                async for chunk in response.aiter_bytes():
                    yield chunk


rime_service = RimeTTSService()
