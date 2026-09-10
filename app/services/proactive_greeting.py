"""
Proactive Greeting Service for SeniorCare
Provides precomputed, cached Rime audio greetings for senior interactions without invoking the LLM.
Enforces TurnSource=PROACTIVE_GREETING and AudioSource=PRECOMPUTED_RIME.
"""

import base64
import uuid
import logging
from typing import Dict, Any, Optional

from app.config import settings
from app.services.voice_response_store import voice_response_store
from app.services.rime_voice_cache import rime_voice_cache, compute_rime_cache_key
from app.services.rime_tts import rime_service
from app.services.voice_orchestrator import turn_state_store

logger = logging.getLogger("ProactiveGreetingService")


class ProactiveGreetingService:
    async def get_or_precompute_greeting(
        self,
        user_id: int,
        user_name: str = "Friend",
        greeting_type: str = "initial_greeting",
        details: Optional[str] = None,
        rime_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Retrieves precomputed Rime audio greeting for a user.
        Bypasses LLM entirely to deliver consistent voice, sub-10ms response, and strict turn fencing.
        """
        cfg = rime_config or {}
        speaker = cfg.get("speaker", getattr(settings, "RIME_SPEAKER", "celeste"))
        model_id = cfg.get("model_id", getattr(settings, "RIME_MODEL_ID", "coda"))
        speed = cfg.get("speed", getattr(settings, "RIME_TIME_SCALE_FACTOR", 1.05))

        rime_cfg = {
            "model_id": model_id,
            "speaker": speaker,
            "speed": speed,
            "language": "en",
            "endpoint": rime_service.api_url,
            "audio_format": "audio/mpeg"
        }

        # 1. Retrieve canonical template
        template_intent = greeting_type if greeting_type in ["initial_greeting", "3_hour_checkin", "medication_due"] else "initial_greeting"
        text = voice_response_store.get_canonical_response(
            context_state="proactive_greeting",
            intent=template_intent,
            user_name=user_name,
            details=details or "prescribed dose"
        )
        if not text:
            text = f"Hello {user_name}! I am Elena, your voice care assistant. How are you feeling today?"

        # 2. Check persistent voice cache
        cached_entry = rime_voice_cache.get("proactive_greeting", template_intent, rime_cfg)
        audio_base64 = ""
        audio_source = "PRECOMPUTED_RIME"

        if cached_entry and cached_entry.text == text:
            audio_base64 = cached_entry.audio_base64
            logger.info(f"[ProactiveGreeting] PRECOMPUTED CACHE HIT for '{user_name}' ({greeting_type})")
        else:
            # Precompute via Rime TTS
            logger.info(f"[ProactiveGreeting] Synthesizing & caching Rime greeting for '{user_name}' ({greeting_type})...")
            try:
                audio_bytes = await rime_service.synthesize(
                    text=text,
                    speaker=speaker,
                    model_id=model_id,
                    speed=speed,
                    audio_format="audio/mpeg"
                )
                entry = rime_voice_cache.put(
                    context_state="proactive_greeting",
                    intent=template_intent,
                    text=text,
                    audio_bytes=audio_bytes,
                    rime_config=rime_cfg,
                    metadata={"response_id": f"proactive_greeting__{template_intent}"}
                )
                audio_base64 = entry.audio_base64
            except Exception as e:
                logger.error(f"[ProactiveGreeting] Failed to synthesize Rime greeting: {e}")
                audio_base64 = ""
                audio_source = "FALLBACK"

        # 3. Create and register distinct assistant turn identity
        turn_id = f"greeting_{uuid.uuid4().hex[:10]}"
        turn_state_store.register_turn(user_id, turn_id)

        return {
            "turn_source": "PROACTIVE_GREETING",
            "audio_source": audio_source,
            "text": text,
            "spoken_text": text,
            "audio_base64": audio_base64,
            "audio_format": "audio/mpeg",
            "turn_id": turn_id,
            "context_state": "wellness_check" if greeting_type != "medication_due" else "medication_check",
            "user_id": user_id,
            "has_proactive_prompt": True,
            "prompt_needed": True
        }


proactive_greeting_service = ProactiveGreetingService()
