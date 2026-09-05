def test_panic_alert_trigger_and_resolve(client):
    # 1. Create patient
    u_res = client.post("/users", json={"name": "Evelyn Vance", "age": 83})
    assert u_res.status_code == 201
    user_id = u_res.json()["id"]

    # 2. Trigger Panic Button
    panic_res = client.post("/caregiver/panic", json={
        "user_id": user_id,
        "note": "Fell in living room",
        "location": "Living Room"
    })
    assert panic_res.status_code == 201
    panic_data = panic_res.json()
    alert_id = panic_data["id"]
    assert panic_data["event_type"] == "PANIC_ALERT"
    assert "Fell in living room" in panic_data["message"]
    assert panic_data["processed"] is False

    # 3. Verify in analytics
    analytics_res = client.get(f"/caregiver/analytics/{user_id}")
    assert analytics_res.status_code == 200
    analytics = analytics_res.json()
    assert analytics["active_alerts_count"] >= 1
    assert any(a["id"] == alert_id for a in analytics["active_alerts"])

    # 4. Resolve Alert
    resolve_res = client.post(f"/caregiver/alerts/{alert_id}/resolve")
    assert resolve_res.status_code == 200
    assert resolve_res.json()["processed"] is True

    # 5. Verify active alert count decreased
    analytics_after = client.get(f"/caregiver/analytics/{user_id}").json()
    assert analytics_after["active_alerts_count"] == 0


def test_caregiver_analytics_aggregations(client):
    # Setup Caregiver and Patient
    cg_res = client.post("/caregivers", json={"name": "Dr. Sarah", "contact": "+1-800-DOC"})
    cg_id = cg_res.json()["id"]

    u_res = client.post("/users", json={"name": "Thomas Hardy", "age": 88, "caregiver_id": cg_id})
    user_id = u_res.json()["id"]

    # Add medication
    med_res = client.post("/medications", json={
        "user_id": user_id,
        "name": "Blood Pressure Med",
        "dosage": "1 tablet",
        "times": ["08:00"]
    })
    med_id = med_res.json()["id"]

    # Log medication intake (Taken)
    client.post("/medication-logs", json={
        "medication_id": med_id,
        "scheduled_time": "08:00",
        "taken": True
    })

    # Log Health Record with pain
    client.post("/health-records", json={
        "user_id": user_id,
        "mood": "tired",
        "sleep": "poor",
        "appetite": "normal",
        "pain": "knee stiffness"
    })

    # Fetch Analytics
    analytics = client.get(f"/caregiver/analytics/{user_id}?days=7").json()
    assert analytics["user_name"] == "Thomas Hardy"
    assert analytics["caregiver_name"] == "Dr. Sarah"
    assert analytics["overall_adherence_rate"] == 100.0
    assert len(analytics["adherence_trend"]) == 7
    assert len(analytics["sleep_trend"]) == 7
    assert len(analytics["pain_logs"]) >= 1
    assert analytics["pain_logs"][0]["pain"] == "knee stiffness"


def test_caregiver_patients_list(client):
    cg_res = client.post("/caregivers", json={"name": "Nurse Joy", "contact": "+1-555-JOY"})
    cg_id = cg_res.json()["id"]

    client.post("/users", json={"name": "Patient One", "age": 75, "caregiver_id": cg_id})
    client.post("/users", json={"name": "Patient Two", "age": 82, "caregiver_id": cg_id})

    patients_res = client.get(f"/caregiver/patients/{cg_id}")
    assert patients_res.status_code == 200
    patients = patients_res.json()
    assert len(patients) == 2
