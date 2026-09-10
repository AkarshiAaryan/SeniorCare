import base64
import json
import logging
import uuid
import time
from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app import models
from app.config import settings
from app.services.stt import stt_service
from app.services.llm_agent import llm_agent
from app.services.rime_tts import rime_service
from app.services.health_extractor import health_extractor
from app.services.voice_nlp import voice_nlp
from app.services.voice_intent_predictor import voice_intent_predictor
from app.services.rime_voice_cache import rime_voice_cache
from app.services.voice_prefetcher import voice_prefetcher

logger = logging.getLogger("VoiceOrchestrator")


class TurnStateStore:
    def __init__(self):
        self.active_turns: Dict[int, str] = {}
        self.turn_history: Dict[int, List[str]] = {}

    def register_turn(self, user_id: int, turn_id: Optional[str]) -> str:
        if not turn_id:
            turn_id = str(uuid.uuid4())

        history = self.turn_history.setdefault(user_id, [])
        if turn_id not in history:
            history.append(turn_id)

        self.active_turns[user_id] = turn_id
        return turn_id

    def is_active_turn(self, user_id: int, turn_id: Optional[str]) -> bool:
        if not turn_id:
            return True

        active_turn = self.active_turns.get(user_id)
        history = self.turn_history.get(user_id, [])

        if active_turn is None:
            return True

        if active_turn == turn_id:
            return True

        if turn_id in history:
            return False

        return True

    def invalidate_user(self, user_id: int) -> None:
        self.active_turns.pop(user_id, None)
        self.turn_history.pop(user_id, None)


turn_state_store = TurnStateStore()


class VoiceOrchestrator:
    async def process_turn(
        self,
        db: Session,
        user_id: int,
        audio_bytes: Optional[bytes] = None,
        text_input: Optional[str] = None,
        filename: str = "audio.wav",
        history: Optional[List[Dict[str, str]]] = None,
        speaker: Optional[str] = None,
        speed: Optional[float] = None,
        turn_id: Optional[str] = None,
        context_state: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Processes a full conversational voice turn with predictive cache acceleration:
        1. Use text_input if provided (e.g. from client live STT), or transcribe audio.
        2. Detect conversational state from context and history.
        3. Perform fast NLP intent classification & urgent symptom safety check.
        4. CACHE HIT: If high confidence intent matches cached Rime audio, serve immediately (sub-10ms).
        5. CACHE MISS: Generate response via LLM and synthesize via Rime TTS.
        6. Asynchronously trigger predictive prefetching for the next turn.
        7. Extract clinical telemetry & persist conversation/health logs to database.
        """
        t0 = time.perf_counter()

        # Fetch user
        user = db.query(models.User).filter(models.User.id == user_id).first()
        if not user:
            raise ValueError(f"User with ID {user_id} not found.")

        turn_id = turn_id or str(uuid.uuid4())
        if not turn_state_store.is_active_turn(user_id, turn_id):
            return {
                "user_text": (text_input or "").strip(),
                "assistant_text": "",
                "audio_base64": "",
                "audio_format": "audio/mpeg",
                "extracted_health": {},
                "history": history or [],
                "conversation_id": None,
                "turn_id": turn_id,
                "stale": True,
                "cached": False,
                "intent": "unknown",
                "context_state": context_state or "wellness_check",
            }
        turn_state_store.register_turn(user_id, turn_id)

        # 1. Speech-to-Text / Input Resolution
        t_stt_start = time.perf_counter()
        user_text = (text_input or "").strip()
        if not user_text and audio_bytes and len(audio_bytes) > 0:
            user_text = await stt_service.transcribe(audio_bytes, filename=filename)

        if not user_text or not user_text.strip():
            user_text = "Hello Elena, I am here."
        t_stt_end = time.perf_counter()
        stt_latency_ms = (t_stt_end - t_stt_start) * 1000

        # 2. Build conversation history & infer context state
        conv_history = history or []
        last_assistant_msg = next((m.get("content", "") for m in reversed(conv_history) if m.get("role") == "assistant"), "")
        active_context_state = context_state or voice_intent_predictor.infer_conversational_state(last_assistant_msg, conv_history)

        # Acoustic Echo Defense: Reject turns where user_text is an acoustic reflection of Elena's speech
        if last_assistant_msg and user_text:
            u_tokens = set(user_text.lower().replace(".", "").replace(",", "").replace("?", "").replace("!", "").split())
            a_tokens = set(last_assistant_msg.lower().replace(".", "").replace(",", "").replace("?", "").replace("!", "").split())
            if u_tokens and len(u_tokens) >= 3:
                overlap = len(u_tokens.intersection(a_tokens)) / len(u_tokens)
                if overlap >= 0.70:
                    logger.warning(f"ACOUSTIC ECHO REJECTED! Utterance matched assistant speech: '{user_text}'")
                    return {
                        "user_text": user_text,
                        "assistant_text": "",
                        "audio_base64": "",
                        "audio_format": "audio/mpeg",
                        "extracted_health": {},
                        "history": conv_history,
                        "conversation_id": None,
                        "turn_id": turn_id,
                        "stale": False,
                        "cached": False,
                        "echo_rejected": True,
                        "intent": "echo_ignored",
                        "confidence": 1.0,
                        "context_state": active_context_state,
                        "latency_ms": {
                            "total": 0.0,
                            "stt": stt_latency_ms,
                            "nlp": 0.0,
                            "cache_lookup": 0.0,
                            "llm": 0.0,
                            "tts": 0.0
                        }
                    }

        conv_history.append({"role": "user", "content": user_text})

        # Fetch user medications and recent health telemetry
        user_meds = db.query(models.Medication).filter(models.Medication.user_id == user_id).all()
        med_names = [m.name for m in user_meds]
        recent_health = db.query(models.HealthRecord).filter(models.HealthRecord.user_id == user_id).order_by(models.HealthRecord.timestamp.desc()).limit(5).all()

        current_hour = datetime.now().hour
        time_of_day = "Morning" if current_hour < 12 else ("Afternoon" if current_hour < 18 else "Evening")

        # 3. Fast NLP Intent & Urgent Safety Analysis
        t_nlp_start = time.perf_counter()
        nlp_result = voice_nlp.classify_intent(user_text, context_state=active_context_state)
        t_nlp_end = time.perf_counter()
        nlp_latency_ms = (t_nlp_end - t_nlp_start) * 1000

        # Rime config parameters
        speaker_to_use = speaker or rime_service.default_speaker
        speed_to_use = speed or rime_service.default_speed
        model_to_use = rime_service.default_model
        rime_cfg = {
            "model_id": model_to_use,
            "speaker": speaker_to_use,
            "speed": speed_to_use,
            "language": "en",
            "endpoint": rime_service.api_url,
            "audio_format": "audio/mpeg"
        }

        # 4. Check Cache Hit (Bypass cache if urgent symptom is detected!)
        is_cache_hit = False
        cache_lookup_latency_ms = 0.0
        ai_response_text = ""
        audio_base64 = ""

        prefetch_enabled = getattr(settings, "PREFETCH_ENABLED", True)
        confidence_threshold = getattr(settings, "PREFETCH_CONFIDENCE_THRESHOLD", 0.75)

        if prefetch_enabled and not nlp_result.is_urgent and nlp_result.confidence >= confidence_threshold and nlp_result.intent != "unknown":
            t_cache_start = time.perf_counter()
            cached_entry = rime_voice_cache.get(active_context_state, nlp_result.intent, rime_cfg)
            t_cache_end = time.perf_counter()
            cache_lookup_latency_ms = (t_cache_end - t_cache_start) * 1000

            if cached_entry:
                is_cache_hit = True
                ai_response_text = cached_entry.text
                audio_base64 = cached_entry.audio_base64
                logger.info(
                    f"PREFETCH CACHE HIT! context={active_context_state}, intent={nlp_result.intent}, "
                    f"confidence={nlp_result.confidence:.2f}, lookup={cache_lookup_latency_ms:.2f}ms"
                )

        # 5. Cache Miss Path: Run Full Generative LLM & Rime Synthesis
        llm_latency_ms = 0.0
        tts_latency_ms = 0.0

        if not is_cache_hit:
            logger.info(f"PREFETCH CACHE MISS: context={active_context_state}, intent={nlp_result.intent}, urgent={nlp_result.is_urgent}")
            t_llm_start = time.perf_counter()
            ai_response_text = await llm_agent.generate_response(
                messages=conv_history,
                user_name=user.name,
                user_age=user.age,
                medications=user_meds,
                health_history=recent_health,
                time_of_day=time_of_day
            )
            t_llm_end = time.perf_counter()
            llm_latency_ms = (t_llm_end - t_llm_start) * 1000

            t_tts_start = time.perf_counter()
            audio_bytes_out = await rime_service.synthesize(
                text=ai_response_text,
                speaker=speaker_to_use,
                speed=speed_to_use,
                audio_format="audio/mpeg"
            )
            t_tts_end = time.perf_counter()
            tts_latency_ms = (t_tts_end - t_tts_start) * 1000
            audio_base64 = base64.b64encode(audio_bytes_out).decode("utf-8")

        conv_history.append({"role": "assistant", "content": ai_response_text})

        # 6. Extract Structured Clinical Data & Persist to Database
        full_transcript = f"User: {user_text}\nAssistant: {ai_response_text}"
        extracted = await health_extractor.extract_from_transcript(full_transcript, known_medications=med_names)

        # If NLP detected an urgent symptom, ensure urgent_alert is flagged True
        if nlp_result.is_urgent:
            extracted["urgent_alert"] = True

        # Database Persistence
        # A. Save Conversation
        db_conv = models.Conversation(
            user_id=user.id,
            transcript=full_transcript,
            extracted_data=json.dumps(extracted),
            timestamp=datetime.now()
        )
        db.add(db_conv)

        # B. Save Health Record if insights were found
        if any(extracted.get(k) and extracted.get(k) != "not reported" for k in ["mood", "sleep", "appetite", "pain"]):
            db_record = models.HealthRecord(
                user_id=user.id,
                timestamp=datetime.now(),
                mood=extracted.get("mood"),
                sleep=extracted.get("sleep"),
                appetite=extracted.get("appetite"),
                pain=extracted.get("pain")
            )
            db.add(db_record)

        # C. Log Medication adherence
        if extracted.get("medication_taken") is not None and user_meds:
            for med in user_meds:
                sched_time = med.schedules[0].time if med.schedules else "08:00"
                db_log = models.MedicationLog(
                    medication_id=med.id,
                    scheduled_time=sched_time,
                    taken=bool(extracted.get("medication_taken")),
                    confirmed_at=datetime.now()
                )
                db.add(db_log)

        # D. Mark pending events as processed
        pending_events = db.query(models.EventLog).filter(
            models.EventLog.user_id == user.id,
            models.EventLog.processed == False
        ).all()
        for ev in pending_events:
            ev.processed = True

        db.commit()
        db.refresh(db_conv)

        # 7. Asynchronously trigger background prefetch for the NEXT turn
        voice_prefetcher.trigger_background_prefetch(
            context_state_or_text=ai_response_text,
            user_name=user.name,
            is_utterance=True,
            rime_config=rime_cfg
        )

        total_latency_ms = (time.perf_counter() - t0) * 1000

        return {
            "user_text": user_text,
            "assistant_text": ai_response_text,
            "audio_base64": audio_base64,
            "audio_format": "audio/mpeg",
            "extracted_health": extracted,
            "history": conv_history,
            "conversation_id": db_conv.id,
            "turn_id": turn_id,
            "stale": False,
            "cached": is_cache_hit,
            "intent": nlp_result.intent,
            "confidence": round(nlp_result.confidence, 3),
            "context_state": active_context_state,
            "latency_ms": {
                "total": round(total_latency_ms, 2),
                "stt": round(stt_latency_ms, 2),
                "nlp": round(nlp_latency_ms, 2),
                "cache_lookup": round(cache_lookup_latency_ms, 2),
                "llm": round(llm_latency_ms, 2),
                "tts": round(tts_latency_ms, 2)
            }
        }


voice_orchestrator = VoiceOrchestrator()
