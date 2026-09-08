import asyncio
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
    """
    try:
        result = await voice_orchestrator.process_turn(
            db=db,
            user_id=req.user_id,
            text_input=req.text_input,
            history=req.history,
            speaker=req.speaker,
            speed=req.speed,
            turn_id=req.turn_id
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
    db: Session = Depends(get_db)
):
    """
    Process an audio or speech-based conversational turn from microphone:
    Audio/Live STT -> LLM response -> Rime TTS -> Data extraction -> DB save.
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
            turn_id=turn_id
        )
        return result
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        logger.error(f"Audio voice turn error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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

    return ProactiveCheckResponse(
        has_proactive_prompt=True,
        prompt_type=req.reason_type,
        text=proactive_text,
        audio_base64=audio_b64,
        audio_format="audio/mpeg",
        event_id=event.id,
        timestamp=event.timestamp.isoformat()
    )



@router.post("/cancel/{user_id}")
def cancel_active_turn(user_id: int):
    """Explicit HTTP endpoint to cancel the currently active turn for a user."""
    prev = voice_orchestrator.turn_state_store.cancel_active_turn(user_id)
    if prev:
        return {"cancelled_turn": prev}
    return {"cancelled_turn": None}


@router.websocket("/ws/{user_id}")
async def voice_websocket_endpoint(websocket: WebSocket, user_id: int):
    """
    Real-time bidirectional WebSocket for streaming voice interactions with elderly users.
    """
    await websocket.accept()
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

        # Keep receiving microphone events while STT/LLM/TTS work runs in a
        # separate task. A new speech_start cancels and supersedes that task.
        current_turn_id = None
        audio_chunks = []
        active_task: Optional[asyncio.Task] = None
        send_lock = asyncio.Lock()

        async def send(payload: dict) -> None:
            async with send_lock:
                await websocket.send_json(payload)

        async def run_turn(turn_id: str, audio_bytes: Optional[bytes] = None, text_input: Optional[str] = None) -> None:
            nonlocal history
            db = SessionLocal()
            stream_started = False

            async def send_audio_chunk(chunk: bytes, sequence: int) -> None:
                nonlocal stream_started
                if not stream_started:
                    stream_started = True
                    await send({"event": "tts_start", "turn_id": turn_id, "audio_format": "audio/mpeg"})
                await send({
                    "event": "tts_chunk",
                    "turn_id": turn_id,
                    "sequence": sequence,
                    "audio": base64.b64encode(chunk).decode("utf-8"),
                })

            try:
                result = await voice_orchestrator.process_turn(
                    db=db,
                    user_id=user_id,
                    audio_bytes=audio_bytes,
                    text_input=text_input,
                    history=list(history),
                    turn_id=turn_id,
                    audio_chunk_handler=send_audio_chunk,
                )
                if result.get("stale"):
                    await send({"event": "stale_turn", "turn_id": turn_id})
                    return
                history = result["history"]
                if stream_started:
                    await send({"event": "tts_end", "turn_id": turn_id})
                await send({
                    "event": "assistant_complete",
                    "turn_id": turn_id,
                    "user_text": result["user_text"],
                    "text": result["assistant_text"],
                    "extracted_health": result["extracted_health"],
                    "history": result["history"],
                })
            except asyncio.CancelledError:
                # The newer speech_start has already invalidated this turn.
                raise
            except Exception as exc:
                logger.error("WebSocket voice turn failed: %s", exc)
                await send({"event": "voice_error", "turn_id": turn_id, "message": "Voice turn failed"})
            finally:
                db.close()

        while True:
            data = await websocket.receive_json()
            event_type = data.get("event")

            if event_type == "speech_start":
                # New speech turn is beginning; register new turn_id and cancel previous
                requested = data.get("turn_id")
                prev_active = voice_orchestrator.turn_state_store.active_turns.get(user_id)
                new_turn = voice_orchestrator.turn_state_store.register_turn(user_id, requested)
                current_turn_id = new_turn
                audio_chunks = []
                if active_task and not active_task.done():
                    active_task.cancel()
                # If a previous active turn existed and differs, notify client to stop playback
                if prev_active and prev_active != new_turn:
                    await websocket.send_json({"event": "turn_invalidated", "turn_id": prev_active})

            elif event_type == "audio_chunk":
                # receive base64 chunk and append
                chunk_b64 = data.get("audio", "")
                if chunk_b64 and data.get("turn_id") == current_turn_id:
                    try:
                        chunk_bytes = base64.b64decode(chunk_b64)
                        audio_chunks.append(chunk_bytes)
                    except Exception:
                        logger.warning("Invalid audio chunk received")

            elif event_type == "speech_end":
                # finalize audio and process turn if still active
                if not current_turn_id:
                    await websocket.send_json({"event": "error", "message": "no active turn"})
                    continue
                if data.get("turn_id") != current_turn_id:
                    continue
                audio_bytes_in = b"".join(audio_chunks)
                active_task = asyncio.create_task(run_turn(current_turn_id, audio_bytes=audio_bytes_in))
                # Clear current turn
                current_turn_id = None
                audio_chunks = []

            elif event_type == "cancel_turn":
                # Explicit cancel requested (e.g., client barge-in)
                prev = voice_orchestrator.turn_state_store.cancel_active_turn(user_id)
                if prev:
                    if active_task and not active_task.done():
                        active_task.cancel()
                    await websocket.send_json({"event": "turn_invalidated", "turn_id": prev})

            elif event_type == "user_text":
                requested = data.get("turn_id")
                prev_active = voice_orchestrator.turn_state_store.active_turns.get(user_id)
                new_turn = voice_orchestrator.turn_state_store.register_turn(user_id, requested)
                if active_task and not active_task.done():
                    active_task.cancel()
                if prev_active and prev_active != new_turn:
                    await send({"event": "turn_invalidated", "turn_id": prev_active})
                active_task = asyncio.create_task(run_turn(new_turn, text_input=data.get("text", "")))

            elif event_type == "ping":
                await websocket.send_json({"event": "pong"})

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for user {user_id}")
    except Exception as e:
        logger.error(f"WebSocket error for user {user_id}: {e}")
    finally:
        if 'active_task' in locals() and active_task and not active_task.done():
            active_task.cancel()
