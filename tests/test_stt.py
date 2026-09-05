import pytest
from app.services.stt import STTService


@pytest.mark.asyncio
async def test_stt_empty_audio():
    stt = STTService()
    transcript = await stt.transcribe(b"")
    assert transcript == ""


@pytest.mark.asyncio
async def test_stt_mock_transcription():
    stt = STTService()
    audio_sample = b"\x00\x01\x02\x03TestAudioData"
    transcript = await stt.transcribe(audio_sample)
    assert isinstance(transcript, str)
    assert len(transcript) > 0
