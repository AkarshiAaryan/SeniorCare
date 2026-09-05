def test_medication_logs_taken_and_missed(client):
    # 1. Setup User & Medication
    u_res = client.post("/users", json={"name": "Helen Mirren", "age": 79})
    user_id = u_res.json()["id"]

    m_res = client.post("/medications", json={
        "user_id": user_id,
        "name": "Atorvastatin",
        "dosage": "20mg",
        "times": ["21:00"]
    })
    med_id = m_res.json()["id"]

    # 2. Log dose as Taken
    log_res1 = client.post("/medication-logs", json={
        "medication_id": med_id,
        "scheduled_time": "21:00",
        "taken": True
    })
    assert log_res1.status_code == 201
    assert log_res1.json()["taken"] is True

    # 3. Log next dose as Missed
    log_res2 = client.post("/medication-logs", json={
        "medication_id": med_id,
        "scheduled_time": "21:00",
        "taken": False
    })
    assert log_res2.status_code == 201
    assert log_res2.json()["taken"] is False

    # 4. Fetch logs for user
    get_logs = client.get(f"/medication-logs/user/{user_id}")
    assert get_logs.status_code == 200
    logs = get_logs.json()
    assert len(logs) == 2


def test_log_for_nonexistent_medication(client):
    res = client.post("/medication-logs", json={
        "medication_id": 9999,
        "scheduled_time": "08:00",
        "taken": True
    })
    assert res.status_code == 404
    assert res.json()["detail"] == "Medication not found"
