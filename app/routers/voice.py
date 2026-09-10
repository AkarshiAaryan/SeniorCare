import json
import base64
import logging
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, WebSocket, WebSocketDisconnect, Response, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime

from app.database import get_db, SessionLocal
from app.services.rime_tts import rime_service
from app.services.stt import stt_service
from app.services.llm_agent import llm_agent
from app.services.voice_orchestrator import voice_orchestrator
from app.services.voice_prefetcher import voice_prefetcher
from app.services.rime_voice_cache import rime_voice_cache
from app import models

logger = logging.getLogger("VoiceRouter")
router = APIRouter(prefix="/voice", tags=["Voice & Conversational AI"])


# --- Schemas for Voice Endpoints ---
class TTSRequest(BaseModel):
    text: str
    speaker: Optional[str] = None
    model_id: Optional[str] = None
    speed: Optional[float] = None


class VoiceTurnRequest(BaseModel):
    user_id: int
    text_input: Optional[str] = None
    speaker: Optional[str] = None
    speed: Optional[float] = None
    history: Optional[List[dict]] = None
    turn_id: Optional[str] = None
    context_state: Optional[str] = None


class VoiceTurnResponse(BaseModel):
    user_text: str
    assistant_text: str
    audio_base64: str
    audio_format: str
    extracted_health: dict
    history: List[dict]
    conversation_id: Optional[int] = None
    turn_id: str = ""
    stale: bool = False
    cached: bool = False
    intent: Optional[str] = None
    confidence: Optional[float] = None
    context_state: Optional[str] = None
    latency_ms: Optional[dict] = None


class PrefetchRequest(BaseModel):
    user_id: Optional[int] = None
    user_name: Optional[str] = "Friend"
    context_state: Optional[str] = "wellness_check"
    assistant_text: Optional[str] = None
    k: Optional[int] = 2


class ProactiveCheckResponse(BaseModel):
    has_proactive_prompt: bool
    prompt_type: Optional[str] = None
    text: Optional[str] = None
    audio_base64: Optional[str] = None
    audio_format: Optional[str] = "audio/mpeg"
    event_id: Optional[int] = None
    timestamp: Optional[str] = None


class ProactiveTriggerRequest(BaseModel):
    user_id: int
    reason_type: str = "3_hour_checkin"  # "3_hour_checkin" or "medication_due"
    details: Optional[str] = "Daily wellness check"



# --- Endpoints ---

@router.post("/tts")
async def generate_tts(req: TTSRequest):
    """
    Generate spoken audio using Rime TTS.
    """
    try:
        audio_bytes = await rime_service.synthesize(
            text=req.text,
            speaker=req.speaker,
            model_id=req.model_id,
            speed=req.speed,
            audio_format="audio/mpeg"
        )
        return Response(content=audio_bytes, media_type="audio/mpeg")
    except Exception as e:
        logger.error(f"TTS generation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stt")
async def transcribe_audio(file: UploadFile = File(...)):
    """
    Transcribe spoken voice audio to text using STT.
    """
    try:
        audio_bytes = await file.read()
        transcript = await stt_service.transcribe(audio_bytes, filename=file.filename or "audio.wav")
        return {"transcript": transcript}
    except Exception as e:
        logger.error(f"STT error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/process-turn", response_model=VoiceTurnResponse)
async def process_turn(
    req: VoiceTurnRequest,
    db: Session = Depends(get_db)
):
    """
    Process a text-based conversational turn: LLM response -> Rime TTS -> Data extraction -> DB save.
    Accelerated with predictive Rime voice cache for instant (sub-10ms) responses.
    """
    try:
        result = await voice_orchestrator.process_turn(
            db=db,
            user_id=req.user_id,
            text_input=req.text_input,
            history=req.history,
            speaker=req.speaker,
            speed=req.speed,
            turn_id=req.turn_id,
            context_state=req.context_state
        )
        return result
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        logger.error(f"Voice turn processing error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/process-audio-turn", response_model=VoiceTurnResponse)
async def process_audio_turn(
    user_id: int = Form(...),
    audio_file: Optional[UploadFile] = File(None),
    text_input: Optional[str] = Form(None),
    history_json: Optional[str] = Form(None),
    speaker: Optional[str] = Form(None),
    speed: Optional[float] = Form(None),
    turn_id: Optional[str] = Form(None),
    context_state: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """
    Process an audio or speech-based conversational turn from microphone:
    Audio/Live STT -> Predictive Cache / LLM response -> Rime TTS -> Data extraction -> DB save.
    """
    try:
        audio_bytes = None
        filename = "audio.wav"
        if audio_file:
            audio_bytes = await audio_file.read()
            filename = audio_file.filename or "audio.wav"

        history = json.loads(history_json) if history_json else []

        result = await voice_orchestrator.process_turn(
            db=db,
            user_id=user_id,
            audio_bytes=audio_bytes,
            text_input=text_input,
            filename=filename,
            history=history,
            speaker=speaker,
            speed=speed,
            turn_id=turn_id,
            context_state=context_state
        )
        return result
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        logger.error(f"Audio voice turn error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/prefetch")
async def prefetch_voice_responses(req: PrefetchRequest, db: Session = Depends(get_db)):
    """
    Explicitly pre-generates and caches Rime TTS responses for anticipated user intents
    in the background for a given context or assistant speech.
    """
    user_name = req.user_name or "Friend"
    if req.user_id:
        user = db.query(models.User).filter(models.User.id == req.user_id).first()
        if user and user.name:
            user_name = user.name

    if req.assistant_text:
        entries = await voice_prefetcher.prefetch_for_assistant_utterance(
            assistant_text=req.assistant_text,
            user_name=user_name,
            k=req.k
        )
    else:
        state = req.context_state or "wellness_check"
        entries = await voice_prefetcher.prefetch_for_context(
            context_state=state,
            user_name=user_name,
            k=req.k
        )

    return {
        "status": "success",
        "prefetched_count": len(entries),
        "cached_entries": [
            {
                "context_state": e.context_state,
                "intent": e.intent,
                "text": e.text,
                "audio_size_bytes": e.audio_size_bytes,
                "cache_key": e.cache_key
            }
            for e in entries
        ]
    }


@router.get("/cache-stats")
async def get_voice_cache_stats():
    """
    Returns statistics and telemetry for the Rime predictive voice cache.
    """
    return rime_voice_cache.get_stats()


@router.delete("/cache")
async def clear_voice_cache():
    """
    Clears in-memory and persistent disk voice cache.
    """
    cleared = rime_voice_cache.clear()
    return {"status": "success", "cleared_entries": cleared}


@router.get("/proactive-check/{user_id}", response_model=ProactiveCheckResponse)
async def check_proactive_outreach(user_id: int, db: Session = Depends(get_db)):
    """
    Polls for automated proactive voice outreach events (Medication Due or 3-Hour Interval Check-in).
    When due, synthesizes a natural, empathetic spoken opening via LLM + Rime TTS.
    """
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Find earliest unprocessed event
    pending_event = db.query(models.EventLog).filter(
        models.EventLog.user_id == user.id,
        models.EventLog.processed == False
    ).order_by(models.EventLog.timestamp.asc()).first()

    if not pending_event:
        return ProactiveCheckResponse(has_proactive_prompt=False)

    reason_type = "medication_due" if pending_event.event_type == "MEDICATION_DUE" else "3_hour_checkin"
    current_hour = datetime.now().hour
    time_of_day = "Morning" if current_hour < 12 else ("Afternoon" if current_hour < 18 else "Evening")

    # Generate natural proactive spoken opening with LLM
    proactive_text = await llm_agent.generate_proactive_outreach(
        user_name=user.name,
        user_age=user.age,
        reason_type=reason_type,
        details=pending_event.message,
        time_of_day=time_of_day
    )

    # Synthesize audio with Rime TTS
    audio_bytes = await rime_service.synthesize(proactive_text)
    audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")

    # Trigger background prefetch for senior's anticipated response
    target_state = "medication_check" if reason_type == "medication_due" else "wellness_check"
    voice_prefetcher.trigger_background_prefetch(
        context_state_or_text=target_state,
        user_name=user.name,
        is_utterance=False
    )

    return ProactiveCheckResponse(
        has_proactive_prompt=True,
        prompt_type=reason_type,
        text=proactive_text,
        audio_base64=audio_b64,
        audio_format="audio/mpeg",
        event_id=pending_event.id,
        timestamp=pending_event.timestamp.isoformat()
    )


@router.post("/proactive-trigger", response_model=ProactiveCheckResponse)
async def trigger_proactive_prompt(req: ProactiveTriggerRequest, db: Session = Depends(get_db)):
    """
    Simulates or forces a proactive outreach trigger (for testing 3-hour check-ins or medication times).
    """
    user = db.query(models.User).filter(models.User.id == req.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    current_hour = datetime.now().hour
    time_of_day = "Morning" if current_hour < 12 else ("Afternoon" if current_hour < 18 else "Evening")

    # Create event in DB
    ev_type = "MEDICATION_DUE" if req.reason_type == "medication_due" else "CHECK_IN_DUE"
    event = models.EventLog(
        event_type=ev_type,
        user_id=user.id,
        message=req.details or f"{time_of_day} check-in",
        timestamp=datetime.now(),
        processed=False
    )
    db.add(event)
    db.commit()
    db.refresh(event)

    # Generate LLM speech
    proactive_text = await llm_agent.generate_proactive_outreach(
        user_name=user.name,
        user_age=user.age,
        reason_type=req.reason_type,
        details=req.details or "Prescription dose",
        time_of_day=time_of_day
    )

    # Synthesize audio with Rime TTS
    audio_bytes = await rime_service.synthesize(proactive_text)
    audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")

    # Trigger background prefetch for senior's anticipated response
    target_state = "medication_check" if req.reason_type == "medication_due" else "wellness_check"
    voice_prefetcher.trigger_background_prefetch(
        context_state_or_text=target_state,
        user_name=user.name,
        is_utterance=False
    )

    return ProactiveCheckResponse(
        has_proactive_prompt=True,
        prompt_type=req.reason_type,
        text=proactive_text,
        audio_base64=audio_b64,
        audio_format="audio/mpeg",
        event_id=event.id,
        timestamp=event.timestamp.isoformat()
    )


@router.websocket("/ws/{user_id}")
async def voice_websocket_endpoint(websocket: WebSocket, user_id: int):
    """
    Real-time bidirectional WebSocket for streaming voice interactions with elderly users.
    """
    await websocket.accept()
    db = SessionLocal()
    history = []
    logger.info(f"WebSocket voice session opened for user {user_id}")

    try:
        # Send initial warm greeting
        greeting_text = "Hello! I am Elena, your care assistant. How are you feeling today?"
        audio_bytes = await rime_service.synthesize(greeting_text)
        audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")

        await websocket.send_json({
            "event": "assistant_response",
            "text": greeting_text,
            "audio_base64": audio_b64
        })
        history.append({"role": "assistant", "content": greeting_text})

        while True:
            data = await websocket.receive_json()
            event_type = data.get("event")

            if event_type == "user_text":
                user_msg = data.get("text", "")
                result = await voice_orchestrator.process_turn(
                    db=db,
                    user_id=user_id,
                    text_input=user_msg,
                    history=history
                )
                history = result["history"]
                await websocket.send_json({
                    "event": "assistant_response",
                    "user_text": result["user_text"],
                    "text": result["assistant_text"],
                    "audio_base64": result["audio_base64"],
                    "extracted_health": result["extracted_health"]
                })

            elif event_type == "user_audio":
                audio_b64_in = data.get("audio_base64", "")
                audio_bytes_in = base64.b64decode(audio_b64_in)
                result = await voice_orchestrator.process_turn(
                    db=db,
                    user_id=user_id,
                    audio_bytes=audio_bytes_in,
                    history=history
                )
                history = result["history"]
                await websocket.send_json({
                    "event": "assistant_response",
                    "user_text": result["user_text"],
                    "text": result["assistant_text"],
                    "audio_base64": result["audio_base64"],
                    "extracted_health": result["extracted_health"]
                })

            elif event_type == "ping":
                await websocket.send_json({"event": "pong"})

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for user {user_id}")
    except Exception as e:
        logger.error(f"WebSocket error for user {user_id}: {e}")
    finally:
        db.close()
