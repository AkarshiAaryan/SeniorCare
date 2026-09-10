"""
Voice Prefetcher Module for SeniorCare
Asynchronously predicts top-K user intents, pre-generates canonical Rime TTS responses,
and populates the persistent voice cache in the background without blocking the UI.
"""

import asyncio
import logging
from typing import List, Optional, Dict, Any

from app.config import settings
from app.services.voice_intent_predictor import voice_intent_predictor
from app.services.voice_response_store import voice_response_store
from app.services.rime_voice_cache import rime_voice_cache, CachedAudioEntry
from app.services.rime_tts import rime_service

logger = logging.getLogger("VoicePrefetcher")


class VoicePrefetcherService:
    def __init__(self):
        self.enabled = getattr(settings, "PREFETCH_ENABLED", True)
        self.default_top_k = getattr(settings, "PREFETCH_TOP_K", 2)

    async def prefetch_for_context(
        self,
        context_state: str,
        user_name: str = "Friend",
        k: Optional[int] = None,
        rime_config: Optional[Dict[str, Any]] = None
    ) -> List[CachedAudioEntry]:
        """
        Prefetches the top-K predicted assistant responses for a given context state.
        Synthesizes missing audio via Rime and stores it into the local cache.
        """
        if not self.enabled:
            return []

        top_k = k if k is not None else self.default_top_k
        top_k = max(1, top_k)

        predicted_intents = voice_intent_predictor.predict_top_k_intents(context_state, k=top_k)
        results: List[CachedAudioEntry] = []

        cfg = rime_config or {}
        speaker = cfg.get("speaker", getattr(settings, "RIME_SPEAKER", "celeste"))
        model_id = cfg.get("model_id", getattr(settings, "RIME_MODEL_ID", "coda"))
        speed = cfg.get("speed", getattr(settings, "RIME_TIME_SCALE_FACTOR", 1.05))

        for intent, prob in predicted_intents:
            if intent == "unknown":
                continue

            # 1. Retrieve canonical response text
            response_text = voice_response_store.get_canonical_response(
                context_state=context_state,
                intent=intent,
                user_name=user_name
            )
            if not response_text:
                continue

            # 2. Check if already present in cache
            existing = rime_voice_cache.get(context_state, intent, cfg)
            if existing:
                results.append(existing)
                continue

            # 3. Synthesize via Rime TTS
            try:
                audio_bytes = await rime_service.synthesize(
                    text=response_text,
                    speaker=speaker,
                    model_id=model_id,
                    speed=speed,
                    audio_format="audio/mpeg"
                )

                # 4. Save to persistent cache
                entry = rime_voice_cache.put(
                    context_state=context_state,
                    intent=intent,
                    text=response_text,
                    audio_bytes=audio_bytes,
                    rime_config={
                        "model_id": model_id,
                        "speaker": speaker,
                        "speed": speed,
                        "language": "en",
                        "endpoint": rime_service.api_url,
                        "audio_format": "audio/mpeg"
                    },
                    metadata={
                        "probability": prob,
                        "response_id": f"{context_state}__{intent}"
                    }
                )
                results.append(entry)
                logger.info(f"Prefetched & cached Rime audio for ({context_state}, {intent}) [p={prob:.2f}]")
            except Exception as e:
                logger.warning(f"Failed to prefetch Rime audio for ({context_state}, {intent}): {e}")

        return results

    async def prefetch_for_assistant_utterance(
        self,
        assistant_text: str,
        user_name: str = "Friend",
        k: Optional[int] = None,
        rime_config: Optional[Dict[str, Any]] = None
    ) -> List[CachedAudioEntry]:
        """
        Infers conversational state from the assistant's speech and prefetches top-K responses.
        """
        state = voice_intent_predictor.infer_conversational_state(assistant_text)
        return await self.prefetch_for_context(
            context_state=state,
            user_name=user_name,
            k=k,
            rime_config=rime_config
        )

    def trigger_background_prefetch(
        self,
        context_state_or_text: str,
        user_name: str = "Friend",
        is_utterance: bool = False,
        k: Optional[int] = None,
        rime_config: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Launches non-blocking prefetching in the background asyncio event loop.
        """
        if not self.enabled:
            return

        try:
            loop = asyncio.get_running_loop()
            if is_utterance:
                coro = self.prefetch_for_assistant_utterance(
                    assistant_text=context_state_or_text,
                    user_name=user_name,
                    k=k,
                    rime_config=rime_config
                )
            else:
                coro = self.prefetch_for_context(
                    context_state=context_state_or_text,
                    user_name=user_name,
                    k=k,
                    rime_config=rime_config
                )
            loop.create_task(coro)
        except RuntimeError:
            # No running event loop (e.g. sync context)
            pass
        except Exception as e:
            logger.warning(f"Error launching background prefetch task: {e}")


voice_prefetcher = VoicePrefetcherService()
