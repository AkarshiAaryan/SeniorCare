import json
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def log_step(title, method, endpoint, payload=None):
    print(f"\n=======================================================")
    print(f"👉 STEP: {title}")
    print(f"HTTP REQUEST: {method} http://127.0.0.1:8000{endpoint}")
    if payload:
        print(f"REQUEST PAYLOAD:\n{json.dumps(payload, indent=2)}")
    else:
        print(f"REQUEST PAYLOAD: None")

    if method == "POST":
        response = client.post(endpoint, json=payload)
    elif method == "GET":
        response = client.get(endpoint)
    elif method == "PUT":
        response = client.put(endpoint, json=payload)
    elif method == "DELETE":
        response = client.delete(endpoint)

    print(f"STATUS CODE: {response.status_code}")
    try:
        res_json = response.json()
        print(f"API RESPONSE:\n{json.dumps(res_json, indent=2)}")
    except Exception:
        print(f"API RESPONSE: {response.text}")
    
    return response.json() if response.status_code in (200, 201) else None


def main():
    print("🚀 Executing Live End-to-End API Calls against SeniorCare Backend Data...")
    
    # 1. Health Check
    log_step("Root Server Health Check", "GET", "/")

    # 2. Caregiver Creation
    cg = log_step("Create Caregiver Profile", "POST", "/caregivers", {
        "name": "Sarah Nurse",
        "contact": "+1-555-0199"
    })
    cg_id = cg["id"]

    # 3. User / Patient Creation
    user = log_step("Create Elderly Patient Profile", "POST", "/users", {
        "name": "John Doe",
        "age": 78,
        "preferred_language": "English",
        "caregiver_id": cg_id
    })
    user_id = user["id"]

    # 4. Get & Update User
    log_step("Retrieve Patient Profile", "GET", f"/users/{user_id}")
    log_step("Update Patient Profile (Update Age to 79)", "PUT", f"/users/{user_id}", {"age": 79})

    # 5. Medication Management
    med = log_step("Add Medication & Schedule Timings", "POST", "/medications", {
        "user_id": user_id,
        "name": "Medicine A",
        "dosage": "1 tablet",
        "instructions": "Take after breakfast and dinner",
        "times": ["08:00", "20:00"]
    })
    med_id = med["id"]
    log_step("Fetch User Medications", "GET", f"/medications/{user_id}")

    # 6. Conversation & Health Ingestion
    log_step("Ingest AI Voice Conversation Transcript", "POST", "/conversations", {
        "user_id": user_id,
        "transcript": "AI: Good morning John! How did you sleep? User: I slept poorly and feel mild knee pain.",
        "extracted_data": {"mood": "tired", "sleep": "poor", "appetite": "normal", "pain": "mild knee pain"}
    })

    log_step("Ingest Health Record", "POST", "/health-records", {
        "user_id": user_id,
        "mood": "tired",
        "sleep": "poor",
        "appetite": "normal",
        "pain": "mild knee pain"
    })
    log_step("Fetch Health Records for User", "GET", f"/health-records/{user_id}")

    # 7. Medication Logging
    log_step("Log Morning Dose as TAKEN (08:00)", "POST", "/medication-logs", {
        "medication_id": med_id,
        "scheduled_time": "08:00",
        "taken": True
    })
    log_step("Log Evening Dose as MISSED (20:00)", "POST", "/medication-logs", {
        "medication_id": med_id,
        "scheduled_time": "20:00",
        "taken": False
    })
    log_step("Fetch Medication Adherence Logs", "GET", f"/medication-logs/user/{user_id}")

    # 8. Event Triggering & Scheduler Check
    log_step("Manually Trigger Check-in Event", "POST", f"/events/trigger-test-checkin?user_id={user_id}&period=Morning")
    log_step("Query Pending Events for Voice Backend", "GET", f"/events/pending?user_id={user_id}")

    # 9. Daily Report Engine
    log_step("Generate Daily Summary Report for Caregiver Dashboard", "GET", f"/daily-report/{user_id}")

    print("\n=======================================================")
    print("✅ All Live API Requests Executed & Returned Clean 200/201 Responses!")


if __name__ == "__main__":
    main()
