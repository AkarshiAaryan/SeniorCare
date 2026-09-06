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


@pytest.mark.asyncio
async def test_stt_uses_gemini_provider(monkeypatch):
    class FakeResponse:
        status_code = 200
        text = ""

        def json(self):
            return {
                "candidates": [
                    {
                        "content": {
                            "parts": [{"text": "I took my medication this morning."}]
                        }
                    }
                ]
            }

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, headers=None, json=None, files=None, data=None):
            assert "generativelanguage.googleapis.com" in url
            assert "generateContent" in url
            return FakeResponse()

    monkeypatch.setattr("app.services.stt.httpx.AsyncClient", FakeClient)

    stt = STTService(provider="gemini")
    stt.gemini_key = "gemini-test-key"

    transcript = await stt.transcribe(b"\x00\x01\x02\x03", filename="audio.wav")

    assert transcript == "I took my medication this morning."
