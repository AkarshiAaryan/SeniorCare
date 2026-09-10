import pytest
from unittest.mock import patch, AsyncMock
from app.services.voice_prefetcher import voice_prefetcher
from app.services.voice_response_store import voice_response_store
from app.services.rime_voice_cache import rime_voice_cache


def test_response_store_lookup():
    # Test canonical responses
    resp = voice_response_store.get_canonical_response("wellness_check", "mood_positive", user_name="Alice")
    assert resp is not None
    assert "Alice" in resp or "wonderful" in resp or "hear" in resp

    resp_med = voice_response_store.get_canonical_response("medication_check", "medication_taken", user_name="Bob")
    assert resp_med is not None
    assert "Bob" in resp_med or "taking" in resp_med or "medicine" in resp_med or "staying on track" in resp_med


@pytest.fixture(autouse=True)
def clear_cache():
    rime_voice_cache.clear()
    yield
    rime_voice_cache.clear()


@pytest.mark.asyncio
async def test_prefetch_for_context():
    # Mock rime_service.synthesize to return fake audio quickly
    with patch("app.services.rime_tts.rime_service.synthesize", new_callable=AsyncMock) as mock_synth:
        mock_synth.return_value = b"PREFETCHED_RIME_AUDIO_BYTES"

        entries = await voice_prefetcher.prefetch_for_context(
            context_state="wellness_check",
            user_name="Eleanor",
            k=2
        )

        assert len(entries) == 2
        for entry in entries:
            assert entry.context_state == "wellness_check"
            assert entry.audio_bytes == b"PREFETCHED_RIME_AUDIO_BYTES"


@pytest.mark.asyncio
async def test_prefetch_for_assistant_utterance():
    with patch("app.services.rime_tts.rime_service.synthesize", new_callable=AsyncMock) as mock_synth:
        mock_synth.return_value = b"UTTERANCE_RIME_AUDIO_BYTES"

        utterance = "Did you remember to take your blood pressure medication this morning?"
        entries = await voice_prefetcher.prefetch_for_assistant_utterance(
            assistant_text=utterance,
            user_name="Eleanor",
            k=2
        )

        assert len(entries) >= 1
        assert entries[0].context_state == "medication_check"
