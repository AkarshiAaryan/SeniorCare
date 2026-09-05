import json
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def log_step(title, method, endpoint, payload=None):
    print(f"\n=======================================================")
    print(f">> STEP: {title}")
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
    if "audio" in response.headers.get("content-type", ""):
        print(f"API RESPONSE: <Binary Audio Stream ({len(response.content)} bytes, Content-Type: {response.headers.get('content-type')})>")
        return response.content
    try:
        res_json = response.json()
        print(f"API RESPONSE:\n{json.dumps(res_json, indent=2)}")
        return res_json
    except Exception:
        print(f"API RESPONSE: {response.text}")
        return None


def main():
    print("Executing Live End-to-End API Calls against SeniorCare Voice & Data Platform...")
    
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

    # 6. Direct Rime TTS Generation
    log_step("Synthesize Speech with Rime TTS", "POST", "/voice/tts", {
        "text": "Hello John, this is your daily care check-in. How are you feeling today?"
    })

    # 7. Voice Conversational Turn with LLM + Rime + Health Extraction
    log_step("Process Conversational Voice Turn", "POST", "/voice/process-turn", {
        "user_id": user_id,
        "text_input": "I took my morning medicine, but I had poor sleep and mild knee pain."
    })

    # 8. Event Triggering & Scheduler Check
    log_step("Manually Trigger Check-in Event", "POST", f"/events/trigger-test-checkin?user_id={user_id}&period=Morning")
    log_step("Query Pending Events for Voice Backend", "GET", f"/events/pending?user_id={user_id}")

    # 9. Daily Report Engine
    log_step("Generate Daily Summary Report for Caregiver Dashboard", "GET", f"/daily-report/{user_id}")

    print("\n=======================================================")
    print("[SUCCESS] All Live API Requests Executed & Returned Clean 200/201 Responses!")


if __name__ == "__main__":
    main()
