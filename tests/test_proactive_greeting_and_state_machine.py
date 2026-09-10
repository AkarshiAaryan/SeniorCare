import pytest
from unittest.mock import patch
from app.services.proactive_greeting import proactive_greeting_service
from app.services.voice_orchestrator import voice_orchestrator, turn_state_store, TurnStateStore
from app import models


@pytest.fixture
def senior_user(db_session):
    user = models.User(
        id=999,
        name="Martha Stewart",
        age=81,
        preferred_language="English"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.mark.asyncio
async def test_1_initial_greeting_uses_precomputed_rime_without_llm(db_session, senior_user):
    """
    TEST 1: Initial proactive greeting MUST use precomputed Rime audio without LLM invocation.
    """
    with patch("app.services.llm_agent.llm_agent.generate_proactive_outreach") as mock_llm:
        greeting = await proactive_greeting_service.get_or_precompute_greeting(
            user_id=senior_user.id,
            user_name=senior_user.name,
            greeting_type="initial_greeting"
        )

        # Assert LLM was NEVER called
        mock_llm.assert_not_called()

        # Assert correct metadata and precomputed audio
        assert greeting["turn_source"] == "PROACTIVE_GREETING"
        assert greeting["audio_source"] == "PRECOMPUTED_RIME"
        assert greeting["turn_id"].startswith("greeting_")
        assert "Martha Stewart" in greeting["text"]
        assert len(greeting["audio_base64"]) > 50
        assert greeting["has_proactive_prompt"] is True


@pytest.mark.asyncio
async def test_2_greeting_completion_registers_turn_in_store(db_session, senior_user):
    """
    TEST 2: Greeting initializes distinct turn state and registers turn ID in TurnStateStore.
    """
    greeting = await proactive_greeting_service.get_or_precompute_greeting(
        user_id=senior_user.id,
        user_name=senior_user.name,
        greeting_type="3_hour_checkin"
    )

    turn_id = greeting["turn_id"]
    assert turn_state_store.is_active_turn(senior_user.id, turn_id) is True


@pytest.mark.asyncio
async def test_3_user_answers_greeting_full_clean_turn(db_session, senior_user):
    """
    TEST 3: User answers greeting -> process_turn executes clean single response without duplicate audio.
    """
    history = [{"role": "assistant", "content": "Hello Martha Stewart! How are you feeling today?"}]
    user_turn_id = "turn_user_001"

    result = await voice_orchestrator.process_turn(
        db=db_session,
        user_id=senior_user.id,
        text_input="I am feeling wonderful today, thank you.",
        history=history,
        turn_id=user_turn_id,
        context_state="wellness_check"
    )

    assert result.get("stale", False) is False
    assert result.get("echo_rejected", False) is False
    assert result["assistant_text"] != ""
    assert result["audio_base64"] != ""
    assert result["turn_id"] == user_turn_id
    assert len(result["history"]) == 3
    assert result["history"][-1]["role"] == "assistant"


@pytest.mark.asyncio
async def test_4_turn_fencing_prevents_audio_overlap(db_session, senior_user):
    """
    TEST 4: When a new turn starts, any in-flight previous turn is marked stale to prevent overlapping audio.
    """
    store = TurnStateStore()
    turn_1 = "turn_001"
    store.register_turn(senior_user.id, turn_1)
    assert store.is_active_turn(senior_user.id, turn_1) is True

    turn_2 = "turn_002"
    store.register_turn(senior_user.id, turn_2)

    # Turn 1 is now stale, Turn 2 is active
    assert store.is_active_turn(senior_user.id, turn_1) is False
    assert store.is_active_turn(senior_user.id, turn_2) is True


@pytest.mark.asyncio
async def test_5_user_interrupts_greeting_creates_new_turn_and_cancels_old(db_session, senior_user):
    """
    TEST 5: User interrupts greeting -> new turn supersedes greeting turn ID.
    """
    greeting = await proactive_greeting_service.get_or_precompute_greeting(
        user_id=senior_user.id,
        user_name=senior_user.name,
        greeting_type="medication_due",
        details="Aspirin 81mg"
    )
    greeting_turn = greeting["turn_id"]

    # User interrupts while greeting is speaking
    interrupt_turn_id = "interrupt_turn_101"
    turn_state_store.register_turn(senior_user.id, interrupt_turn_id)

    assert turn_state_store.is_active_turn(senior_user.id, greeting_turn) is False
    assert turn_state_store.is_active_turn(senior_user.id, interrupt_turn_id) is True


@pytest.mark.asyncio
async def test_6_stale_response_discarded_by_orchestrator(db_session, senior_user):
    """
    TEST 6: Stale turn completion is flagged as stale by voice_orchestrator.
    """
    store = TurnStateStore()
    turn_old = "old_stale_turn"
    turn_new = "new_active_turn"

    store.register_turn(senior_user.id, turn_old)
    store.register_turn(senior_user.id, turn_new)

    with patch("app.services.voice_orchestrator.turn_state_store", store):
        result = await voice_orchestrator.process_turn(
            db=db_session,
            user_id=senior_user.id,
            text_input="I took my pill already.",
            turn_id=turn_old
        )

        assert result["stale"] is True
        assert result["assistant_text"] == ""
        assert result["audio_base64"] == ""


@pytest.mark.asyncio
async def test_7_acoustic_echo_discarded(db_session, senior_user):
    """
    TEST 7: Assistant speech echo captured by mic is flagged and discarded without triggering an assistant response.
    """
    assistant_speech = "Hello Martha Stewart! I am Elena, your voice care assistant. How are you feeling today?"
    history = [{"role": "assistant", "content": assistant_speech}]

    # Simulating microphone picking up the exact assistant greeting playback
    echo_mic_input = "Hello Martha Stewart I am Elena your voice care assistant how are you feeling"

    result = await voice_orchestrator.process_turn(
        db=db_session,
        user_id=senior_user.id,
        text_input=echo_mic_input,
        history=history,
        turn_id="turn_echo_test"
    )

    assert result["echo_rejected"] is True
    assert result["assistant_text"] == ""
    assert result["audio_base64"] == ""


def test_8_full_multi_turn_conversation_cycle(client, senior_user):
    """
    TEST 8: Full multi-turn conversation cycle with strict turn ownership and health logging.
    """
    # 1. Fetch initial proactive greeting via API
    res_greet = client.get(f"/voice/greeting/{senior_user.id}")
    assert res_greet.status_code == 200
    greet_data = res_greet.json()
    assert greet_data["audio_source"] == "PRECOMPUTED_RIME"
    assert "Martha Stewart" in greet_data["text"]

    history = [{"role": "assistant", "content": greet_data["text"]}]

    # 2. Senior Turn 1: Reports knee pain and mood
    res_turn1 = client.post("/voice/process-turn", json={
        "user_id": senior_user.id,
        "text_input": "My right knee is aching quite a bit today, but my mood is okay.",
        "history": history,
        "turn_id": "turn_1"
    })
    assert res_turn1.status_code == 200
    turn1_data = res_turn1.json()
    assert turn1_data.get("stale", False) is False
    assert turn1_data.get("echo_rejected", False) is False
    assert turn1_data["assistant_text"] != ""
    assert turn1_data["audio_base64"] != ""
    history = turn1_data["history"]

    # 3. Senior Turn 2: Confirms medication taken
    res_turn2 = client.post("/voice/process-turn", json={
        "user_id": senior_user.id,
        "text_input": "Yes, I took my morning blood pressure pill with breakfast.",
        "history": history,
        "turn_id": "turn_2"
    })
    assert res_turn2.status_code == 200
    turn2_data = res_turn2.json()
    assert turn2_data.get("stale", False) is False
    assert turn2_data.get("echo_rejected", False) is False
    assert turn2_data["assistant_text"] != ""
    assert len(turn2_data["history"]) == 5
