from datetime import datetime


def test_daily_report_generation(client):
    # 1. Setup User & Medication
    u_res = client.post("/users", json={"name": "Robert Deniro", "age": 81})
    user_id = u_res.json()["id"]

    m_res = client.post("/medications", json={
        "user_id": user_id,
        "name": "Heart Pill",
        "dosage": "5mg",
        "times": ["08:00"]
    })
    med_id = m_res.json()["id"]

    # 2. Add Health Record
    client.post("/health-records", json={
        "user_id": user_id,
        "mood": "tired",
        "sleep": "poor",
        "appetite": "normal",
        "pain": "mild back pain"
    })

    # 3. Add Medication Log
    client.post("/medication-logs", json={
        "medication_id": med_id,
        "scheduled_time": "08:00",
        "taken": True
    })

    # 4. Generate Report
    today_str = datetime.now().strftime("%Y-%m-%d")
    rep_res = client.get(f"/daily-report/{user_id}?target_date={today_str}")
    assert rep_res.status_code == 200
    report = rep_res.json()
    assert report["user_name"] == "Robert Deniro"
    assert report["health_summary"]["sleep"] == "poor"
    assert report["health_summary"]["pain"] == "mild back pain"
    assert len(report["medication_summary"]) == 1
    assert report["medication_summary"][0]["status"] == "Taken"
    assert any("back pain" in n for n in report["notes"])


def test_daily_report_invalid_date(client):
    u_res = client.post("/users", json={"name": "Test User", "age": 70})
    user_id = u_res.json()["id"]

    res = client.get(f"/daily-report/{user_id}?target_date=invalid-date")
    assert res.status_code == 400
    assert "Invalid date format" in res.json()["detail"]
