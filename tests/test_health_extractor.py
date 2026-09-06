import pytest
from app.services.health_extractor import HealthExtractorService


@pytest.mark.asyncio
async def test_health_extraction_symptoms_and_adherence():
    extractor = HealthExtractorService()
    transcript = "User: I didn't sleep well last night and my knee hurts, but I took my morning medicine.\nAssistant: I understand."
    extracted = await extractor.extract_from_transcript(transcript, known_medications=["Aspirin"])
    
    assert extracted["sleep"] == "poor"
    assert "knee" in extracted["pain"]
    assert extracted["medication_taken"] is True
    assert extracted["urgent_alert"] is False


@pytest.mark.asyncio
async def test_health_extraction_missed_medication():
    extractor = HealthExtractorService()
    transcript = "User: I felt lonely and I forgot to take my morning pill today."
    extracted = await extractor.extract_from_transcript(transcript)
    
    assert extracted["mood"] in ["sad", "lonely", "tired", "low", "normal"]
    assert extracted["medication_taken"] is False


@pytest.mark.asyncio
async def test_health_extraction_empty_transcript():
    extractor = HealthExtractorService()
    extracted = await extractor.extract_from_transcript("")
    assert extracted["mood"] == "not reported"
    assert extracted["sleep"] == "not reported"
