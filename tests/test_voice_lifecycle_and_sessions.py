import time
from datetime import datetime, timedelta
import pytest
from unittest.mock import patch
from app.services.voice_session_manager import voice_session_manager, VoiceSessionManager
from app.services.proactive_greeting import proactive_greeting_service
from app.services.voice_orchestrator import voice_orchestrator, turn_state_store, TurnStateStore
from app import models


@pytest.fixture
def senior_user(db_session):
    user = models.User(
        id=777,
        name="Dorothy Gale",
        age=85,
        preferred_language="English"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture(autouse=True)
def clean_session_manager():
    """Ensure a clean session manager and turn state store for each test."""
    voice_session_manager.sessions.clear()
    voice_session_manager.conversations.clear()
    voice_session_manager.user_to_session.clear()
    turn_state_store.active_turns.clear()
    turn_state_store.turn_history.clear()
    yield
    voice_session_manager.sessions.clear()
    voice_session_manager.conversations.clear()
    voice_session_manager.user_to_session.clear()
    turn_state_store.active_turns.clear()
    turn_state_store.turn_history.clear()


# =========================================================================
# TEST 1: Initial Greeting Played ONLY ONCE Per Session
# =========================================================================
def test_1_initial_greeting_played_only_once_per_session(client, senior_user):
    """
    TEST 1: On a new session, greeting is needed. After user answers, subsequent
    requests and turns NEVER trigger the initial greeting again.
    """
    # 1. Init session
    res1 = client.get(f"/voice/session/{senior_user.id}")
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["greeting_needed"] is True
    assert data1["greeting"] is not None
    assert "Dorothy" in data1["greeting"]["text"]
    session_id = data1["session_id"]
    conv_id = data1["conversation_id"]

    # 2. Senior answers greeting
    turn1 = client.post("/voice/process-turn", json={
        "user_id": senior_user.id,
        "text_input": "I am feeling wonderful today, thank you.",
        "session_id": session_id,
        "conversation_id": conv_id,
        "turn_id": "turn_1"
    })
    assert turn1.status_code == 200
    turn1_data = turn1.json()
    assert turn1_data["assistant_text"] != ""
    assert "Dorothy Gale, how are you" not in turn1_data["assistant_text"]

    # 3. Check session again -> greeting_needed MUST be False
    res2 = client.get(f"/voice/session/{senior_user.id}")
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["session_id"] == session_id
    assert data2["greeting_needed"] is False
    assert data2["greeting"] is None


# =========================================================================
# TEST 2: Conversation Context Retained Across User Turns
# =========================================================================
def test_2_conversation_context_retained_across_user_turns(client, senior_user):
    """
    TEST 2: Context is maintained across turns so the LLM has multi-turn history.
    """
    # Init session
    res_init = client.get(f"/voice/session/{senior_user.id}")
    session_id = res_init.json()["session_id"]
    conv_id = res_init.json()["conversation_id"]

    # Turn 1: State specific symptom
    res1 = client.post("/voice/process-turn", json={
        "user_id": senior_user.id,
        "text_input": "I have a sharp pain in my left wrist.",
        "session_id": session_id,
        "conversation_id": conv_id,
        "turn_id": "turn_wrist_1"
    })
    assert res1.status_code == 200
    hist1 = res1.json()["history"]
    assert len(hist1) >= 2

    # Turn 2: Follow-up referencing wrist without saying the word wrist
    res2 = client.post("/voice/process-turn", json={
        "user_id": senior_user.id,
        "text_input": "It started when I woke up this morning.",
        "session_id": session_id,
        "conversation_id": conv_id,
        "history": hist1,
        "turn_id": "turn_wrist_2"
    })
    assert res2.status_code == 200
    hist2 = res2.json()["history"]
    assert len(hist2) >= 4

    # Verify server conversation context stores the turns
    conv = voice_session_manager.get_conversation(conv_id)
    assert conv is not None
    assert any("wrist" in m.get("content", "") for m in conv.history if m.get("role") == "user")


# =========================================================================
# TEST 3: Multi-Turn Dialogue Across Session (4 consecutive turns)
# =========================================================================
def test_3_multiturn_dialogue_across_session(client, senior_user):
    """
    TEST 3: 4 consecutive turns execute cleanly with incrementing turns and context retention.
    """
    res_init = client.get(f"/voice/session/{senior_user.id}")
    session_id = res_init.json()["session_id"]
    conv_id = res_init.json()["conversation_id"]

    turns = [
        "Good morning Elena, I slept very well.",
        "I took my blood pressure tablet at 8 AM.",
        "What time is lunch today?",
        "Thank you Elena, that is all for now."
    ]

    current_history = res_init.json().get("history", [])

    for idx, user_text in enumerate(turns):
        res = client.post("/voice/process-turn", json={
            "user_id": senior_user.id,
            "text_input": user_text,
            "session_id": session_id,
            "conversation_id": conv_id,
            "history": current_history,
            "turn_id": f"multi_turn_{idx+1}"
        })
        assert res.status_code == 200
        data = res.json()
        assert data.get("stale", False) is False
        assert data.get("echo_rejected", False) is False
        assert data["assistant_text"] != ""
        current_history = data["history"]

    conv = voice_session_manager.get_conversation(conv_id)
    assert conv.turn_count == 4


# =========================================================================
# TEST 4: Frontend Remount / Re-render Does NOT Restart Greeting
# =========================================================================
def test_4_frontend_remount_does_not_restart_greeting(client, senior_user):
    """
    TEST 4: When VoiceModal re-mounts (e.g. after onUpdate re-render or closing/reopening),
    the session manager returns the active session with greeting_needed=False.
    """
    # 1. Mount 1
    mount1 = client.get(f"/voice/session/{senior_user.id}")
    session_id = mount1.json()["session_id"]
    assert mount1.json()["greeting_needed"] is True

    # 2. Complete 1 turn
    client.post("/voice/process-turn", json={
        "user_id": senior_user.id,
        "text_input": "I am doing well.",
        "session_id": session_id,
        "turn_id": "turn_remount_1"
    })

    # 3. Simulate Frontend Component Remount (e.g. state refresh or user reopen)
    remount = client.get(f"/voice/session/{senior_user.id}")
    assert remount.status_code == 200
    remount_data = remount.json()
    assert remount_data["session_id"] == session_id
    assert remount_data["greeting_needed"] is False
    assert remount_data["greeting"] is None
    assert len(remount_data["history"]) >= 2


# =========================================================================
# TEST 5: WebSocket Reconnect Does NOT Restart Greeting
# =========================================================================
def test_5_websocket_reconnect_does_not_restart_greeting(client, senior_user):
    """
    TEST 5: WebSocket reconnection for an existing session does not replay initial greeting audio.
    """
    # 1. First connection triggers initial greeting
    with client.websocket_connect(f"/voice/ws/{senior_user.id}") as ws1:
        init_msg = ws1.receive_json()
        assert init_msg["event"] == "assistant_response"
        assert "Dorothy" in init_msg["text"]

        ws1.send_json({"event": "user_text", "text": "Hello Elena!"})
        resp = ws1.receive_json()
        assert resp["event"] == "assistant_response"

    # 2. Reconnection (same user within session window)
    with client.websocket_connect(f"/voice/ws/{senior_user.id}") as ws2:
        # Send ping/pong - should NOT receive an unsolicited duplicate greeting
        ws2.send_json({"event": "ping"})
        pong = ws2.receive_json()
        assert pong["event"] == "pong"


# =========================================================================
# TEST 6: STT Restart Mid-Conversation Preserves Session
# =========================================================================
def test_6_stt_restart_mid_conversation(client, senior_user):
    """
    TEST 6: Restarting speech recognition / sending subsequent turns preserves session and turn state.
    """
    res_init = client.get(f"/voice/session/{senior_user.id}")
    session_id = res_init.json()["session_id"]
    conv_id = res_init.json()["conversation_id"]

    res1 = client.post("/voice/process-turn", json={
        "user_id": senior_user.id,
        "text_input": "First utterance before STT restart.",
        "session_id": session_id,
        "conversation_id": conv_id,
        "turn_id": "stt_turn_1"
    })
    assert res1.status_code == 200

    # STT restarted on client -> new turn ID, same session/conversation
    res2 = client.post("/voice/process-turn", json={
        "user_id": senior_user.id,
        "text_input": "Second utterance after STT restart.",
        "session_id": session_id,
        "conversation_id": conv_id,
        "turn_id": "stt_turn_2"
    })
    assert res2.status_code == 200
    assert res2.json()["session_id"] == session_id
    assert res2.json()["conversation_id"] == conv_id


# =========================================================================
# TEST 7: Rime Audio Playback Completion Flow
# =========================================================================
@pytest.mark.asyncio
async def test_7_rime_audio_playback_completion_transitions(db_session, senior_user):
    """
    TEST 7: Precomputed greeting generates valid Rime audio and registers turn state.
    """
    greeting = await proactive_greeting_service.get_or_precompute_greeting(
        user_id=senior_user.id,
        user_name=senior_user.name,
        greeting_type="initial_greeting"
    )
    assert greeting["audio_source"] == "PRECOMPUTED_RIME"
    assert len(greeting["audio_base64"]) > 50
    assert turn_state_store.is_active_turn(senior_user.id, greeting["turn_id"]) is True


# =========================================================================
# TEST 8: Session Expiry (3 Hours) Creates New Session With Greeting
# =========================================================================
def test_8_session_expiry_3_hours_creates_new_session_with_greeting(client, senior_user):
    """
    TEST 8: After 3 hours TTL expires, the next interaction creates a brand new session
    and delivers a new proactive greeting.
    """
    # 1. Create first session
    res1 = client.get(f"/voice/session/{senior_user.id}")
    session_1_id = res1.json()["session_id"]
    assert res1.json()["greeting_needed"] is True

    # Complete 1 turn to mark greeting sent
    client.post("/voice/process-turn", json={
        "user_id": senior_user.id,
        "text_input": "Hello",
        "session_id": session_1_id,
        "turn_id": "t1"
    })

    # 2. Fast-forward session expiration past 3 hours
    sess_obj = voice_session_manager.sessions[session_1_id]
    sess_obj.expires_at = datetime.now() - timedelta(seconds=1)

    res2 = client.get(f"/voice/session/{senior_user.id}")
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["session_id"] != session_1_id
    assert data2["greeting_needed"] is True
    assert data2["greeting"] is not None


# =========================================================================
# TEST 9: Session Validity Within 3 Hours Reuses Session
# =========================================================================
def test_9_session_validity_within_3_hours(client, senior_user):
    """
    TEST 9: Within 3 hours, the existing session is preserved and reused.
    """
    res1 = client.get(f"/voice/session/{senior_user.id}")
    session_1_id = res1.json()["session_id"]

    # Session is active and within 3 hour TTL
    res2 = client.get(f"/voice/session/{senior_user.id}")
    assert res2.status_code == 200
    assert res2.json()["session_id"] == session_1_id


# =========================================================================
# TEST 10: Stale Response Discarded by Turn Fencing
# =========================================================================
def test_10_stale_response_discarded_turn_fencing(client, senior_user):
    """
    TEST 10: If a turn ID is superseded, any late processing is marked stale.
    """
    res_init = client.get(f"/voice/session/{senior_user.id}")
    session_id = res_init.json()["session_id"]

    # Register turn 1 then turn 2
    turn_state_store.register_turn(senior_user.id, "turn_old_fenced")
    turn_state_store.register_turn(senior_user.id, "turn_new_fenced")

    # Attempt to process old turn
    res = client.post("/voice/process-turn", json={
        "user_id": senior_user.id,
        "text_input": "Old superseded turn text",
        "session_id": session_id,
        "turn_id": "turn_old_fenced"
    })
    assert res.status_code == 200
    assert res.json()["stale"] is True
    assert res.json()["assistant_text"] == ""


# =========================================================================
# TEST 11: Proactive Check-In Scheduler During Active Conversation
# =========================================================================
def test_11_proactive_checkin_scheduler_during_active_conversation(client, senior_user):
    """
    TEST 11: If user is actively talking (within 5-min conversation window),
    background check-in does not interrupt.
    """
    # Init active conversation
    res_init = client.get(f"/voice/session/{senior_user.id}")
    assert voice_session_manager.is_user_in_active_conversation(senior_user.id) is True

    # Check proactive outreach endpoint -> MUST skip prompt while conversation is active
    outreach = client.get(f"/voice/proactive-check/{senior_user.id}")
    assert outreach.status_code == 200
    assert outreach.json()["has_proactive_prompt"] is False


# =========================================================================
# TEST 12: Duplicate Session Initialization Idempotency
# =========================================================================
def test_12_duplicate_session_initialization_idempotency(client, senior_user):
    """
    TEST 12: Multiple repeated calls to /voice/session/{user_id} return identical
    session_id and do not reset greeting_sent or conversation context.
    """
    res1 = client.get(f"/voice/session/{senior_user.id}")
    s1 = res1.json()["session_id"]
    c1 = res1.json()["conversation_id"]

    res2 = client.get(f"/voice/session/{senior_user.id}")
    s2 = res2.json()["session_id"]
    c2 = res2.json()["conversation_id"]

    res3 = client.get(f"/voice/session/{senior_user.id}")
    s3 = res3.json()["session_id"]
    c3 = res3.json()["conversation_id"]

    assert s1 == s2 == s3
    assert c1 == c2 == c3


# =========================================================================
# TEST 13: Duplicate Frontend Mount Session Guard
# =========================================================================
def test_13_duplicate_frontend_mount_session_guard(client, senior_user):
    """
    TEST 13: POST /voice/session or GET /voice/session from multiple frontend
    instances cleanly resolves to the single authoritative session.
    """
    init_post = client.post("/voice/session", json={
        "user_id": senior_user.id,
        "greeting_type": "initial_greeting",
        "force_new": False
    })
    assert init_post.status_code == 200
    post_data = init_post.json()

    init_get = client.get(f"/voice/session/{senior_user.id}")
    assert init_get.status_code == 200
    get_data = init_get.json()

    assert post_data["session_id"] == get_data["session_id"]
    assert post_data["conversation_id"] == get_data["conversation_id"]
