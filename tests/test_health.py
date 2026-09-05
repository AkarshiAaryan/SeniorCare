def test_create_and_get_health_records(client):
    # 1. Create User
    u_res = client.post("/users", json={"name": "Alice Cooper", "age": 77})
    user_id = u_res.json()["id"]

    # 2. Add Health Record
    h_res = client.post("/health-records", json={
        "user_id": user_id,
        "mood": "calm",
        "sleep": "good",
        "appetite": "normal",
        "pain": "none reported"
    })
    assert h_res.status_code == 201
    h_data = h_res.json()
    assert h_data["mood"] == "calm"
    assert h_data["sleep"] == "good"

    # 3. Retrieve Health Records
    get_h = client.get(f"/health-records/{user_id}")
    assert get_h.status_code == 200
    records = get_h.json()
    assert len(records) == 1
    assert records[0]["mood"] == "calm"


def test_create_conversation_transcript(client):
    u_res = client.post("/users", json={"name": "Alice Cooper", "age": 77})
    user_id = u_res.json()["id"]

    conv_res = client.post("/conversations", json={
        "user_id": user_id,
        "transcript": "AI: Good morning! User: Feeling wonderful today.",
        "extracted_data": {"mood": "good", "pain": "none"}
    })
    assert conv_res.status_code == 201
    conv_data = conv_res.json()
    assert "Feeling wonderful" in conv_data["transcript"]
    assert conv_data["extracted_data"] is not None
