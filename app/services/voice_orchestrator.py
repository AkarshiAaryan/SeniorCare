import base64
import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app import models
from app.services.stt import stt_service
from app.services.llm_agent import llm_agent
from app.services.rime_tts import rime_service
from app.services.health_extractor import health_extractor

logger = logging.getLogger("VoiceOrchestrator")


class VoiceOrchestrator:
    async def process_turn(
        self,
        db: Session,
        user_id: int,
        audio_bytes: Optional[bytes] = None,
        text_input: Optional[str] = None,
        history: Optional[List[Dict[str, str]]] = None,
        speaker: Optional[str] = None,
        speed: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Processes a full conversational voice turn:
        1. Transcribe audio if provided, else use text_input.
        2. Fetch user profile, prescribed medications, and context from DB.
        3. Generate empathetic 'Writing for the Ear' response via LLM.
        4. Synthesize spoken audio using Rime TTS.
        5. Extract structured health & medication data.
        6. Persist conversation, health record, and medication adherence logs.
        """
        # Fetch user
        user = db.query(models.User).filter(models.User.id == user_id).first()
        if not user:
            raise ValueError(f"User with ID {user_id} not found.")

        # 1. Speech-to-Text
        if audio_bytes and len(audio_bytes) > 0:
            user_text = await stt_service.transcribe(audio_bytes, filename=f"user_{user_id}.wav")
        else:
            user_text = text_input or ""

        if not user_text.strip():
            user_text = "Hello Elena, I am here."

        # 2. Build conversation history
        conv_history = history or []
        conv_history.append({"role": "user", "content": user_text})

        # Fetch user medications
        user_meds = db.query(models.Medication).filter(models.Medication.user_id == user_id).all()
        med_names = [m.name for m in user_meds]

        # 3. LLM Response Generation
        ai_response_text = await llm_agent.generate_response(
            messages=conv_history,
            user_name=user.name,
            user_age=user.age,
            medications=user_meds
        )

        conv_history.append({"role": "assistant", "content": ai_response_text})

        # 4. Rime TTS Speech Synthesis
        audio_bytes_out = await rime_service.synthesize(
            text=ai_response_text,
            speaker=speaker,
            speed=speed,
            audio_format="audio/mpeg"
        )
        audio_base64 = base64.b64encode(audio_bytes_out).decode("utf-8")

        # 5. Extract structured clinical data
        full_transcript = f"User: {user_text}\nAssistant: {ai_response_text}"
        extracted = await health_extractor.extract_from_transcript(full_transcript, known_medications=med_names)

        # 6. Database Persistence
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
                # Find matching schedule or log latest
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

        return {
            "user_text": user_text,
            "assistant_text": ai_response_text,
            "audio_base64": audio_base64,
            "audio_format": "audio/mpeg",
            "extracted_health": extracted,
            "history": conv_history,
            "conversation_id": db_conv.id
        }


voice_orchestrator = VoiceOrchestrator()
