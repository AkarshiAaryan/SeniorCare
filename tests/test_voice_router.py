import io


def test_voice_tts_endpoint(client):
    res = client.post("/voice/tts", json={"text": "Hello, how are you today?"})
    assert res.status_code == 200
    assert "audio" in res.headers.get("content-type", "")
    assert len(res.content) > 0


def test_voice_stt_endpoint(client):
    fake_audio = io.BytesIO(b"\x00\x01\x02\x03DummyAudioBytes")
    res = client.post("/voice/stt", files={"file": ("test.wav", fake_audio, "audio/wav")})
    assert res.status_code == 200
    assert "transcript" in res.json()


def test_voice_process_turn_endpoint(client):
    # 1. Create User
    u_res = client.post("/users", json={"name": "Morgan Freeman", "age": 87})
    user_id = u_res.json()["id"]

    # 2. Add Medication
    client.post("/medications", json={
        "user_id": user_id,
        "name": "Blood Pressure Med",
        "dosage": "1 tablet",
        "times": ["08:00"]
    })

    # 3. Process Turn via Text
    res = client.post("/voice/process-turn", json={
        "user_id": user_id,
        "text_input": "I took my medicine on time, but I had poor sleep."
    })
    assert res.status_code == 200
    data = res.json()
    assert "assistant_text" in data
    assert "audio_base64" in data
    assert data["extracted_health"]["sleep"] == "poor"
    assert data["extracted_health"]["medication_taken"] is True


def test_voice_proactive_check_and_trigger(client):
    # 1. Create User
    u_res = client.post("/users", json={"name": "Patrick Stewart", "age": 84})
    user_id = u_res.json()["id"]

    # Check proactive prompt when no events exist
    check_empty = client.get(f"/voice/proactive-check/{user_id}")
    assert check_empty.status_code == 200
    assert check_empty.json()["has_proactive_prompt"] is False

    # Trigger proactive prompt (Medication Due)
    trig_res = client.post("/voice/proactive-trigger", json={
        "user_id": user_id,
        "reason_type": "medication_due",
        "details": "Lisinopril 10mg"
    })
    assert trig_res.status_code == 200
    trig_data = trig_res.json()
    assert trig_data["has_proactive_prompt"] is True
    assert "Patrick" in trig_data["text"]
    assert "Lisinopril" in trig_data["text"]
    assert len(trig_data["audio_base64"]) > 0

    # Query proactive check (should find the pending event)
    check_pending = client.get(f"/voice/proactive-check/{user_id}")
    assert check_pending.status_code == 200
    assert check_pending.json()["has_proactive_prompt"] is True


def test_voice_process_turn_nonexistent_user(client):
    res = client.post("/voice/process-turn", json={
        "user_id": 99999,
        "text_input": "Hello Elena"
    })
    assert res.status_code == 404


def test_voice_process_turn_rejects_stale_turn(client):
    u_res = client.post("/users", json={"name": "Alice Parker", "age": 79})
    user_id = u_res.json()["id"]

    old_turn = client.post("/voice/process-turn", json={
        "user_id": user_id,
        "text_input": "What medicines do I take tonight?",
        "turn_id": "turn-old"
    })
    assert old_turn.status_code == 200

    new_turn = client.post("/voice/process-turn", json={
        "user_id": user_id,
        "text_input": "Actually, only tell me about my blood pressure medicine.",
        "turn_id": "turn-new"
    })
    assert new_turn.status_code == 200

    stale_turn = client.post("/voice/process-turn", json={
        "user_id": user_id,
        "text_input": "Ignore that, I still want the old result.",
        "turn_id": "turn-old"
    })
    assert stale_turn.status_code == 200
    assert stale_turn.json().get("stale") is True


def test_voice_websocket_endpoint(client):
    u_res = client.post("/users", json={"name": "Maggie Smith", "age": 89})
    user_id = u_res.json()["id"]

    with client.websocket_connect(f"/voice/ws/{user_id}") as websocket:
        # Initial greeting received
        init_data = websocket.receive_json()
        assert init_data["event"] == "assistant_response"
        assert "Elena" in init_data["text"]

        # Send ping
        websocket.send_json({"event": "ping"})
        pong_data = websocket.receive_json()
        assert pong_data["event"] == "pong"

        # Send user text turn
        websocket.send_json({"event": "user_text", "text": "I took my morning medicine and feel great."})
        turn_resp = websocket.receive_json()
        assert turn_resp["event"] == "assistant_response"
        assert "text" in turn_resp
        assert "audio_base64" in turn_resp
