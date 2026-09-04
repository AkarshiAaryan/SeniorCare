import pytest
from fastapi.testclient import TestClient
from datetime import datetime

from app.main import app
from app.database import Base, engine, SessionLocal
from app import models

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db():
    # Recreate tables before tests
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


def test_full_senior_care_workflow():
    # --- 1. Phase 3: Caregiver & Patient APIs ---
    # Create Caregiver
    res = client.post("/caregivers", json={"name": "Sarah Nurse", "contact": "+1-555-0199"})
    assert res.status_code == 201
    caregiver = res.json()
    caregiver_id = caregiver["id"]
    assert caregiver["name"] == "Sarah Nurse"

    # Create Patient/User
    res = client.post("/users", json={
        "name": "John Doe",
        "age": 78,
        "preferred_language": "English",
        "caregiver_id": caregiver_id
    })
    assert res.status_code == 201
    user = res.json()
    user_id = user["id"]
    assert user["name"] == "John Doe"

    # Get User
    res = client.get(f"/users/{user_id}")
    assert res.status_code == 200
    assert res.json()["id"] == user_id

    # Update User
    res = client.put(f"/users/{user_id}", json={"age": 79})
    assert res.status_code == 200
    assert res.json()["age"] == 79

    # --- 2. Phase 4: Medication Management APIs ---
    # Create Medication with schedule timings
    res = client.post("/medications", json={
        "user_id": user_id,
        "name": "Medicine A",
        "dosage": "1 tablet",
        "instructions": "Take after meal",
        "times": ["08:00", "20:00"]
    })
    assert res.status_code == 201
    med = res.json()
    med_id = med["id"]
    assert med["name"] == "Medicine A"
    assert len(med["schedules"]) == 2

    # Get User Medications
    res = client.get(f"/medications/{user_id}")
    assert res.status_code == 200
    assert len(res.json()) == 1

    # --- 3. Phase 6: Health Record & Conversation Ingestion ---
    # Save Conversation
    res = client.post("/conversations", json={
        "user_id": user_id,
        "transcript": "AI: How are you feeling today? User: I slept poorly and have mild knee pain.",
        "extracted_data": {"mood": "tired", "sleep": "poor", "appetite": "normal", "pain": "mild knee pain"}
    })
    assert res.status_code == 201

    # Save Health Record
    res = client.post("/health-records", json={
        "user_id": user_id,
        "mood": "tired",
        "sleep": "poor",
        "appetite": "normal",
        "pain": "mild knee pain"
    })
    assert res.status_code == 201
    health_rec = res.json()
    assert health_rec["mood"] == "tired"

    # --- 4. Phase 8: Medication Logging ---
    # Log intake for morning dose (Taken)
    res = client.post("/medication-logs", json={
        "medication_id": med_id,
        "scheduled_time": "08:00",
        "taken": True
    })
    assert res.status_code == 201
    assert res.json()["taken"] is True

    # Log intake for evening dose (Missed)
    res = client.post("/medication-logs", json={
        "medication_id": med_id,
        "scheduled_time": "20:00",
        "taken": False
    })
    assert res.status_code == 201
    assert res.json()["taken"] is False

    # --- 5. Event trigger test ---
    res = client.post(f"/events/trigger-test-checkin?user_id={user_id}&period=Morning")
    assert res.status_code == 201

    res = client.get(f"/events/pending?user_id={user_id}")
    assert res.status_code == 200
    assert len(res.json()) >= 1

    # --- 6. Phase 9: Daily Report Engine ---
    today_str = datetime.now().strftime("%Y-%m-%d")
    res = client.get(f"/daily-report/{user_id}?target_date={today_str}")
    assert res.status_code == 200
    report = res.json()
    assert report["user_name"] == "John Doe"
    assert report["health_summary"]["sleep"] == "poor"
    assert report["health_summary"]["pain"] == "mild knee pain"
    assert len(report["medication_summary"]) == 2
    assert "User reported: mild knee pain" in report["notes"] or any("knee" in n for n in report["notes"])

    print("\nSUCCESS: All MVP tests passed clean!")


if __name__ == "__main__":
    pytest.main(["-v", __file__])
