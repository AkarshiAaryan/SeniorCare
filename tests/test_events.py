def test_events_lifecycle(client):
    # 1. Setup User
    u_res = client.post("/users", json={"name": "Samuel Jackson", "age": 75})
    user_id = u_res.json()["id"]

    # 2. Trigger test check-in event
    ev_res = client.post(f"/events/trigger-test-checkin?user_id={user_id}&period=Morning")
    assert ev_res.status_code == 201
    event_data = ev_res.json()
    event_id = event_data["id"]
    assert event_data["processed"] is False
    assert "Morning check-in is due" in event_data["message"]

    # 3. Query Pending Events
    pending_res = client.get(f"/events/pending?user_id={user_id}")
    assert pending_res.status_code == 200
    events = pending_res.json()
    assert len(events) >= 1
    assert events[0]["id"] == event_id

    # 4. Acknowledge Event
    ack_res = client.post(f"/events/{event_id}/acknowledge")
    assert ack_res.status_code == 200
    assert ack_res.json()["processed"] is True

    # 5. Query Pending Events again (should now be empty)
    pending_res2 = client.get(f"/events/pending?user_id={user_id}")
    assert pending_res2.status_code == 200
    assert len(pending_res2.json()) == 0
