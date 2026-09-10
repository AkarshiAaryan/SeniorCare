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
from app.services.proactive_greeting import proactive_greeting_service
from app.services.voice_session_manager import voice_session_manager
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
    session_id: Optional[str] = None
    conversation_id: Optional[str] = None
    context_state: Optional[str] = None


class VoiceTurnResponse(BaseModel):
    user_text: str
    assistant_text: str
    audio_base64: str
    audio_format: str
    extracted_health: dict
    history: List[dict]
    conversation_id: Optional[str] = None
    db_conversation_id: Optional[int] = None
    session_id: Optional[str] = None
    turn_id: str = ""
    stale: bool = False
    cached: bool = False
    echo_rejected: bool = False
    intent: Optional[str] = None
    confidence: Optional[float] = None
    context_state: Optional[str] = None
    latency_ms: Optional[dict] = None


class SessionInitRequest(BaseModel):
    user_id: int
    greeting_type: Optional[str] = "initial_greeting"
    details: Optional[str] = None
    force_new: Optional[bool] = False


class SessionInitResponse(BaseModel):
    session_id: str
    conversation_id: str
    user_id: int
    greeting_needed: bool
    greeting: Optional[dict] = None
    history: List[dict] = []
    expires_at: str


class PrefetchRequest(BaseModel):
    user_id: Optional[int] = None
    user_name: Optional[str] = "Friend"
    context_state: Optional[str] = "wellness_check"
    assistant_text: Optional[str] = None
    k: Optional[int] = 2


class ProactiveCheckResponse(BaseModel):
    has_proactive_prompt: bool
    prompt_needed: Optional[bool] = None
    prompt_type: Optional[str] = None
    text: Optional[str] = None
    spoken_text: Optional[str] = None
    audio_base64: Optional[str] = None
    audio_format: Optional[str] = "audio/mpeg"
    event_id: Optional[int] = None
    timestamp: Optional[str] = None
    turn_id: Optional[str] = None
    turn_source: Optional[str] = None
    audio_source: Optional[str] = None
    context_state: Optional[str] = None


class GreetingRequest(BaseModel):
    user_id: int
    greeting_type: Optional[str] = "initial_greeting"
    details: Optional[str] = None


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
            session_id=req.session_id,
            conversation_id=req.conversation_id,
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
    session_id: Optional[str] = Form(None),
    conversation_id: Optional[str] = Form(None),
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
            session_id=session_id,
            conversation_id=conversation_id,
            context_state=context_state
        )
        return result
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        logger.error(f"Audio voice turn error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/session/{user_id}", response_model=SessionInitResponse)
async def get_or_init_voice_session(
    user_id: int,
    greeting_type: str = "initial_greeting",
    details: Optional[str] = None,
    force_new: bool = False,
    db: Session = Depends(get_db)
):
    """
    Initializes or retrieves the authoritative 3-hour voice session and 5-minute active conversation.
    Ensures initial precomputed Rime greeting is returned exactly ONCE per session.
    """
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    sess, is_new_session = voice_session_manager.get_or_create_session(user_id, force_new=force_new)
    conv, _ = voice_session_manager.get_or_create_conversation(sess.session_id, user_id, force_new=force_new)

    greeting_needed = is_new_session or not sess.greeting_sent
    greeting_data = None

    if greeting_needed:
        greeting_data = await proactive_greeting_service.get_or_precompute_greeting(
            user_id=user.id,
            user_name=user.name,
            greeting_type=greeting_type,
            details=details,
            session_id=sess.session_id,
            conversation_id=conv.conversation_id
        )
        voice_session_manager.mark_greeting_sent(sess.session_id, greeting_data.get("spoken_text") or greeting_data.get("text"))

    return SessionInitResponse(
        session_id=sess.session_id,
        conversation_id=conv.conversation_id,
        user_id=user.id,
        greeting_needed=greeting_needed,
        greeting=greeting_data,
        history=conv.history,
        expires_at=sess.expires_at.isoformat()
    )


@router.post("/session", response_model=SessionInitResponse)
async def post_init_voice_session(
    req: SessionInitRequest,
    db: Session = Depends(get_db)
):
    return await get_or_init_voice_session(
        user_id=req.user_id,
        greeting_type=req.greeting_type or "initial_greeting",
        details=req.details,
        force_new=bool(req.force_new),
        db=db
    )


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


@router.get("/greeting/{user_id}")
async def get_user_greeting(
    user_id: int,
    greeting_type: str = "initial_greeting",
    details: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Returns precomputed, cached Rime audio greeting for a user.
    Bypasses LLM entirely to prevent voice mismatch, provide deterministic tone, and reduce latency.
    """
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    greeting = await proactive_greeting_service.get_or_precompute_greeting(
        user_id=user.id,
        user_name=user.name,
        greeting_type=greeting_type,
        details=details
    )
    return greeting


@router.post("/greeting")
async def post_user_greeting(
    req: GreetingRequest,
    db: Session = Depends(get_db)
):
    """
    POST variant to retrieve precomputed Rime audio greeting.
    """
    user = db.query(models.User).filter(models.User.id == req.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    greeting = await proactive_greeting_service.get_or_precompute_greeting(
        user_id=user.id,
        user_name=user.name,
        greeting_type=req.greeting_type or "initial_greeting",
        details=req.details
    )
    return greeting


@router.get("/proactive-check/{user_id}", response_model=ProactiveCheckResponse)
async def check_proactive_outreach(user_id: int, db: Session = Depends(get_db)):
    """
    Polls for automated proactive voice outreach events (Medication Due or 3-Hour Interval Check-in).
    When due, retrieves precomputed Rime audio greeting without invoking LLM dynamically.
    """
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # If senior is currently in an active conversation (< 5 min), do not disrupt with proactive check-in
    if voice_session_manager.is_user_in_active_conversation(user_id):
        return ProactiveCheckResponse(has_proactive_prompt=False, prompt_needed=False)

    # Find earliest unprocessed event
    pending_event = db.query(models.EventLog).filter(
        models.EventLog.user_id == user.id,
        models.EventLog.processed == False
    ).order_by(models.EventLog.timestamp.asc()).first()

    if not pending_event:
        return ProactiveCheckResponse(has_proactive_prompt=False, prompt_needed=False)

    reason_type = "medication_due" if pending_event.event_type == "MEDICATION_DUE" else "3_hour_checkin"

    # Retrieve precomputed Rime greeting
    greeting = await proactive_greeting_service.get_or_precompute_greeting(
        user_id=user.id,
        user_name=user.name,
        greeting_type=reason_type,
        details=pending_event.message
    )

    # Trigger background prefetch for senior's anticipated response
    target_state = "medication_check" if reason_type == "medication_due" else "wellness_check"
    voice_prefetcher.trigger_background_prefetch(
        context_state_or_text=target_state,
        user_name=user.name,
        is_utterance=False
    )

    return ProactiveCheckResponse(
        has_proactive_prompt=True,
        prompt_needed=True,
        prompt_type=reason_type,
        text=greeting["text"],
        spoken_text=greeting["spoken_text"],
        audio_base64=greeting["audio_base64"],
        audio_format="audio/mpeg",
        turn_id=greeting["turn_id"],
        turn_source=greeting["turn_source"],
        audio_source=greeting["audio_source"],
        context_state=greeting["context_state"],
        event_id=pending_event.id,
        timestamp=pending_event.timestamp.isoformat()
    )


@router.post("/proactive-trigger", response_model=ProactiveCheckResponse)
async def trigger_proactive_prompt(req: ProactiveTriggerRequest, db: Session = Depends(get_db)):
    """
    Simulates or forces a proactive outreach trigger (for testing 3-hour check-ins or medication times).
    Uses precomputed Rime audio greeting without invoking LLM dynamically.
    """
    user = db.query(models.User).filter(models.User.id == req.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    current_hour = datetime.now().hour
    time_of_day = "Morning" if current_hour < 12 else ("Afternoon" if current_hour < 18 else "Evening")

    norm_reason = (req.reason_type or "").lower().strip()
    ev_type = "MEDICATION_DUE" if "med" in norm_reason else "CHECK_IN_DUE"
    greeting_type = "medication_due" if "med" in norm_reason else "3_hour_checkin"

    # Create event in DB
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

    # Retrieve precomputed Rime greeting
    greeting = await proactive_greeting_service.get_or_precompute_greeting(
        user_id=user.id,
        user_name=user.name,
        greeting_type=greeting_type,
        details=req.details or "Prescription dose"
    )

    # Trigger background prefetch for senior's anticipated response
    target_state = "medication_check" if ev_type == "MEDICATION_DUE" else "wellness_check"
    voice_prefetcher.trigger_background_prefetch(
        context_state_or_text=target_state,
        user_name=user.name,
        is_utterance=False
    )

    return ProactiveCheckResponse(
        has_proactive_prompt=True,
        prompt_needed=True,
        prompt_type=req.reason_type,
        text=greeting["text"],
        spoken_text=greeting["spoken_text"],
        audio_base64=greeting["audio_base64"],
        audio_format="audio/mpeg",
        turn_id=greeting["turn_id"],
        turn_source=greeting["turn_source"],
        audio_source=greeting["audio_source"],
        context_state=greeting["context_state"],
        event_id=event.id,
        timestamp=event.timestamp.isoformat()
    )


@router.websocket("/ws/{user_id}")
async def voice_websocket_endpoint(websocket: WebSocket, user_id: int, db: Session = Depends(get_db)):
    """
    Real-time bidirectional WebSocket for streaming voice interactions with elderly users.
    Uses VoiceSessionManager to preserve conversational context across reconnects.
    """
    await websocket.accept()
    logger.info(f"WebSocket voice session opened for user {user_id}")

    try:
        sess, is_new = voice_session_manager.get_or_create_session(user_id)
        conv, _ = voice_session_manager.get_or_create_conversation(sess.session_id, user_id)
        history = list(conv.history)

        # Send initial warm greeting ONLY if new session or greeting not yet sent
        if is_new or not sess.greeting_sent:
            user = db.query(models.User).filter(models.User.id == user_id).first()
            user_name = user.name if user else "Friend"
            greeting = await proactive_greeting_service.get_or_precompute_greeting(
                user_id=user_id,
                user_name=user_name,
                session_id=sess.session_id,
                conversation_id=conv.conversation_id
            )
            voice_session_manager.mark_greeting_sent(sess.session_id, greeting.get("spoken_text") or greeting.get("text"))
            await websocket.send_json({
                "event": "assistant_response",
                "text": greeting["spoken_text"],
                "audio_base64": greeting["audio_base64"],
                "session_id": sess.session_id,
                "conversation_id": conv.conversation_id
            })
            history = conv.history

        while True:
            data = await websocket.receive_json()
            event_type = data.get("event")

            if event_type == "user_text":
                user_msg = data.get("text", "")
                result = await voice_orchestrator.process_turn(
                    db=db,
                    user_id=user_id,
                    text_input=user_msg,
                    history=history,
                    session_id=sess.session_id,
                    conversation_id=conv.conversation_id
                )
                history = result["history"]
                await websocket.send_json({
                    "event": "assistant_response",
                    "user_text": result["user_text"],
                    "text": result["assistant_text"],
                    "audio_base64": result["audio_base64"],
                    "extracted_health": result["extracted_health"],
                    "session_id": result["session_id"],
                    "conversation_id": result["conversation_id"]
                })

            elif event_type == "user_audio":
                audio_b64_in = data.get("audio_base64", "")
                audio_bytes_in = base64.b64decode(audio_b64_in)
                result = await voice_orchestrator.process_turn(
                    db=db,
                    user_id=user_id,
                    audio_bytes=audio_bytes_in,
                    history=history,
                    session_id=sess.session_id,
                    conversation_id=conv.conversation_id
                )
                history = result["history"]
                await websocket.send_json({
                    "event": "assistant_response",
                    "user_text": result["user_text"],
                    "text": result["assistant_text"],
                    "audio_base64": result["audio_base64"],
                    "extracted_health": result["extracted_health"],
                    "session_id": result["session_id"],
                    "conversation_id": result["conversation_id"]
                })

            elif event_type == "ping":
                await websocket.send_json({"event": "pong"})

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for user {user_id}")
    except Exception as e:
        logger.error(f"WebSocket error for user {user_id}: {e}")
    finally:
        db.close()
