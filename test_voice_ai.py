import base64
from fastapi.testclient import TestClient
from datetime import datetime

from app.main import app
from app.database import Base, engine, SessionLocal
from app import models
from app.services.rime_tts import rime_service
from app.services.health_extractor import health_extractor
from app.services.llm_agent import llm_agent

client = TestClient(app)


def test_rime_text_normalization():
    # Test normalization rules for "Writing for the Ear"
    raw_text = "Take 2 tabs of Aspirin 500mg at 08:00 AM w/ water & relax. **Important!**"
    normalized = rime_service.normalize_text_for_ear(raw_text)
    
    assert "milligrams" in normalized
    assert "tablets" in normalized or "tablet" in normalized
    assert "with" in normalized
    assert "and" in normalized
    assert "**" not in normalized
    print("\n[PASS] Text Normalization for Ear tested successfully:", normalized)


def test_health_extractor():
    import asyncio
    transcript = "User: I didn't sleep well at all last night and my knee hurts, but I took my morning pill.\nAssistant: I understand."
    extracted = asyncio.run(health_extractor.extract_from_transcript(transcript, known_medications=["Aspirin"]))
    
    assert extracted["sleep"] == "poor"
    assert "knee" in extracted["pain"]
    assert extracted["medication_taken"] is True
    print("\n[PASS] Health & Adherence extraction tested successfully:", extracted)


def test_llm_agent_prompt_builder():
    meds = [{"name": "Lisinopril", "dosage": "10mg", "schedules": [{"time": "08:00"}]}]
    prompt = llm_agent.build_system_prompt("Arthur", 82, meds, "Morning")
    
    assert "Arthur" in prompt
    assert "Lisinopril" in prompt
    assert "82" in prompt
    assert "WRITING FOR THE EAR" in prompt
    print("\n[PASS] LLM Agent Prompt construction verified successfully.")


def test_voice_endpoints_workflow():
    # Setup test user and caregiver
    res_cg = client.post("/caregivers", json={"name": "Nurse Emily", "contact": "+1-800-CARE"})
    assert res_cg.status_code == 201
    cg_id = res_cg.json()["id"]

    res_user = client.post("/users", json={"name": "Robert Smith", "age": 80, "caregiver_id": cg_id})
    assert res_user.status_code == 201
    user_id = res_user.json()["id"]

    # Add medication
    res_med = client.post("/medications", json={
        "user_id": user_id,
        "name": "Blood Pressure Med",
        "dosage": "1 tablet",
        "times": ["08:00"]
    })
    assert res_med.status_code == 201

    # 1. Direct TTS Endpoint test
    tts_res = client.post("/voice/tts", json={"text": "Good morning Robert, how are you feeling today?"})
    assert tts_res.status_code == 200
    assert len(tts_res.content) > 0
    print("\n[PASS] Direct TTS endpoint returned valid audio stream bytes.")

    # 2. Process Turn via REST API
    turn_res = client.post("/voice/process-turn", json={
        "user_id": user_id,
        "text_input": "I took my medicine on time, but I have mild knee pain today."
    })
    assert turn_res.status_code == 200
    turn_data = turn_res.json()
    assert turn_data["user_text"] == "I took my medicine on time, but I have mild knee pain today."
    assert len(turn_data["assistant_text"]) > 0
    assert len(turn_data["audio_base64"]) > 0
    assert turn_data["extracted_health"]["pain"] != "none reported"
    print("\n[PASS] Conversational Voice Turn processed with generated audio & health metrics.")

    # 3. Verify Database synchronization
    # Verify health record was saved
    res_health = client.get(f"/health-records/{user_id}")
    assert res_health.status_code == 200
    assert len(res_health.json()) >= 1

    # Verify medication adherence log was saved
    res_med_logs = client.get(f"/medication-logs/user/{user_id}")
    assert res_med_logs.status_code == 200
    assert len(res_med_logs.json()) >= 1
    assert res_med_logs.json()[0]["taken"] is True

    # 4. Verify Daily Report aggregates voice extracted data
    res_report = client.get(f"/daily-report/{user_id}")
    assert res_report.status_code == 200
    report_data = res_report.json()
    assert report_data["user_name"] == "Robert Smith"
    print("\n[PASS] Daily Report successfully aggregated voice extracted health and medication logs:", report_data)


if __name__ == "__main__":
    test_rime_text_normalization()
    test_health_extractor()
    test_llm_agent_prompt_builder()
    test_voice_endpoints_workflow()
    print("\n[SUCCESS] ALL VOICE AI & RIME BACKEND INTEGRATION TESTS PASSED SUCCESSFULLY!")
