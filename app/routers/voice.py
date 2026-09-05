import json
import base64
import logging
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, WebSocket, WebSocketDisconnect, Response, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db, SessionLocal
from app.services.rime_tts import rime_service
from app.services.stt import stt_service
from app.services.voice_orchestrator import voice_orchestrator

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


class VoiceTurnResponse(BaseModel):
    user_text: str
    assistant_text: str
    audio_base64: str
    audio_format: str
    extracted_health: dict
    history: List[dict]
    conversation_id: int


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
            speed=req.speed
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
    audio_file: UploadFile = File(...),
    history_json: Optional[str] = Form(None),
    speaker: Optional[str] = Form(None),
    speed: Optional[float] = Form(None),
    db: Session = Depends(get_db)
):
    """
    Process an audio-based conversational turn from microphone:
    Audio -> STT -> LLM response -> Rime TTS -> Data extraction -> DB save.
    """
    try:
        audio_bytes = await audio_file.read()
        history = json.loads(history_json) if history_json else []

        result = await voice_orchestrator.process_turn(
            db=db,
            user_id=user_id,
            audio_bytes=audio_bytes,
            history=history,
            speaker=speaker,
            speed=speed
        )
        return result
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        logger.error(f"Audio voice turn error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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
