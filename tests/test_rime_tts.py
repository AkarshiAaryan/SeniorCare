import pytest
from app.services.rime_tts import RimeTTSService, rime_service


def test_text_normalization_for_ear():
    tts = RimeTTSService()
    raw = "Take 2 tabs of Aspirin 500mg at 08:00 AM w/ water & relax. **Never miss your dose!**"
    normalized = tts.normalize_text_for_ear(raw)
    
    assert "500 milligrams" in normalized
    assert "2 tablets" in normalized
    assert "with" in normalized
    assert "and" in normalized
    assert "**" not in normalized
    assert "08 o'clock AM" in normalized


def test_empty_text_normalization():
    tts = RimeTTSService()
    assert tts.normalize_text_for_ear("") == ""


@pytest.mark.asyncio
async def test_rime_synthesize_mock_fallback():
    # Test synthesis with default mock fallback when no API key is provided
    tts = RimeTTSService(api_key="")
    audio_bytes = await tts.synthesize("Hello world")
    assert isinstance(audio_bytes, bytes)
    assert len(audio_bytes) > 0


@pytest.mark.asyncio
async def test_rime_stream_synthesize_mock_fallback():
    tts = RimeTTSService(api_key="")
    chunks = []
    async for chunk in tts.stream_synthesize("Hello world streaming"):
        chunks.append(chunk)
    assert len(chunks) >= 1
    assert len(b"".join(chunks)) > 0
