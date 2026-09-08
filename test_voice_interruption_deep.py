import asyncio
import json
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.database import Base, engine
from app.services.voice_orchestrator import voice_orchestrator, turn_state_store

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    turn_state_store.invalidate_user(1)
    yield


def test_turn_invalidation_and_cancellation_logic():
    # 1. Register Turn 1
    t1 = turn_state_store.register_turn(user_id=1, turn_id="turn-1")
    assert t1 == "turn-1"
    assert turn_state_store.is_active_turn(user_id=1, turn_id="turn-1") is True

    # 2. Register Turn 2 for same user -> Turn 1 must be marked as cancelled/stale
    t2 = turn_state_store.register_turn(user_id=1, turn_id="turn-2")
    assert t2 == "turn-2"
    assert turn_state_store.is_active_turn(user_id=1, turn_id="turn-2") is True
    assert turn_state_store.is_active_turn(user_id=1, turn_id="turn-1") is False

    # 3. Explicit turn cancellation
    cancelled = turn_state_store.cancel_active_turn(user_id=1)
    assert cancelled == "turn-2"
    assert turn_state_store.is_active_turn(user_id=1, turn_id="turn-2") is False


def test_process_turn_rejects_stale_turn_id():
    u_res = client.post("/users", json={"name": "John Interrupted", "age": 80})
    user_id = u_res.json()["id"]

    # Start turn-1
    res1 = client.post("/voice/process-turn", json={
        "user_id": user_id,
        "text_input": "I have knee pain",
        "turn_id": "turn-1"
    })
    assert res1.status_code == 200
    assert res1.json()["stale"] is False

    # User barges in with turn-2
    res2 = client.post("/voice/process-turn", json={
        "user_id": user_id,
        "text_input": "Actually, cancel that, tell me about my medicine.",
        "turn_id": "turn-2"
    })
    assert res2.status_code == 200
    assert res2.json()["stale"] is False

    # Older turn-1 tries to complete or send request -> MUST be rejected as stale
    res1_stale = client.post("/voice/process-turn", json={
        "user_id": user_id,
        "text_input": "I have knee pain",
        "turn_id": "turn-1"
    })
    assert res1_stale.status_code == 200
    assert res1_stale.json()["stale"] is True
    assert res1_stale.json()["assistant_text"] == ""


def test_explicit_cancel_endpoint():
    u_res = client.post("/users", json={"name": "Sarah Test", "age": 75})
    user_id = u_res.json()["id"]

    # Start turn
    client.post("/voice/process-turn", json={
        "user_id": user_id,
        "text_input": "Hello Elena",
        "turn_id": "turn-active"
    })

    # Call HTTP cancellation endpoint
    c_res = client.post(f"/voice/cancel/{user_id}")
    assert c_res.status_code == 200
    assert c_res.json()["cancelled_turn"] == "turn-active"

    # Subsequent request with turn-active must be stale
    stale_res = client.post("/voice/process-turn", json={
        "user_id": user_id,
        "text_input": "Hello Elena",
        "turn_id": "turn-active"
    })
    assert stale_res.json()["stale"] is True


if __name__ == "__main__":
    pytest.main(["-v", __file__])
