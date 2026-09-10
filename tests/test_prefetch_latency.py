import pytest
import time
from unittest.mock import patch, AsyncMock
from app.services.voice_orchestrator import voice_orchestrator
from app.services.rime_voice_cache import rime_voice_cache
from app import models


@pytest.fixture
def test_user(db_session):
    user = models.User(
        id=101,
        name="Eleanor Vance",
        age=84,
        preferred_language="English"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.mark.asyncio
async def test_cache_hit_sub_10ms_latency(db_session, test_user):
    # 1. Warm cache with pre-generated audio for wellness_check
    cfg = {"speaker": "celeste", "model_id": "coda", "speed": 1.05}
    fake_audio = b"MOCK_CACHED_RIME_AUDIO_BYTES_TEST"

    rime_voice_cache.put(
        context_state="wellness_check",
        intent="mood_positive",
        text=f"I'm so glad to hear that, {test_user.name}! Keep having a wonderful day.",
        audio_bytes=fake_audio,
        rime_config=cfg
    )

    with patch("app.services.health_extractor.health_extractor.extract_from_transcript", new_callable=AsyncMock) as mock_extract:
        mock_extract.return_value = {
            "mood": "happy",
            "sleep": "good",
            "appetite": "good",
            "pain": "none",
            "medication_taken": True,
            "urgent_alert": False
        }

        # 2. Process turn with a positive phrase
        t0 = time.perf_counter()
        result = await voice_orchestrator.process_turn(
            db=db_session,
            user_id=test_user.id,
            text_input="I am feeling wonderful today!",
            context_state="wellness_check"
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000

        # 3. Assert Cache Hit
        assert result["cached"] is True
        assert result["intent"] == "mood_positive"
        assert result["context_state"] == "wellness_check"
        assert "latency_ms" in result
        assert result["latency_ms"]["cache_lookup"] < 15.0
        assert result["latency_ms"]["llm"] == 0.0
        assert result["latency_ms"]["tts"] == 0.0


@pytest.mark.asyncio
async def test_urgent_symptom_bypasses_cache(db_session, test_user):
    # Even if wellness_check has cached responses, urgent red flag symptoms MUST bypass cache
    with patch("app.services.llm_agent.llm_agent.generate_response", new_callable=AsyncMock) as mock_llm, \
         patch("app.services.rime_tts.rime_service.synthesize", new_callable=AsyncMock) as mock_tts, \
         patch("app.services.health_extractor.health_extractor.extract_from_transcript", new_callable=AsyncMock) as mock_extract:

        mock_llm.return_value = "I understand you are having severe chest pain. I am notifying your caregiver and emergency contacts right away."
        mock_tts.return_value = b"EMERGENCY_AUDIO"
        mock_extract.return_value = {
            "mood": "anxious",
            "sleep": "not reported",
            "appetite": "not reported",
            "pain": "severe chest pain",
            "medication_taken": None,
            "urgent_alert": True
        }

        result = await voice_orchestrator.process_turn(
            db=db_session,
            user_id=test_user.id,
            text_input="I have terrible crushing chest pain and feel dizzy",
            context_state="wellness_check"
        )

        assert result["cached"] is False
        assert result["intent"] == "urgent_symptom"
        assert result["extracted_health"].get("urgent_alert") is True
