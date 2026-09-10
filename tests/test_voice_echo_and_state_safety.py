import pytest
import time
from unittest.mock import patch, AsyncMock
from app.services.voice_orchestrator import voice_orchestrator, TurnStateStore
from app import models


@pytest.fixture
def senior_user(db_session):
    user = models.User(
        id=777,
        name="Arthur Pendelton",
        age=82,
        preferred_language="English"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.mark.asyncio
async def test_regression_assistant_listens_to_itself_is_rejected(db_session, senior_user):
    """
    CRITICAL REGRESSION TEST:
    Simulates acoustic echo where the assistant speaks:
    "Hello Arthur! It is wonderful to speak with you today. How are you feeling this morning?"
    And the microphone receives that exact same sentence as audio/transcript.
    
    EXPECTED:
    - Backend echo defense detects high lexical overlap with prior assistant turn.
    - Result has echo_rejected=True.
    - No new assistant response is generated.
    - No infinite conversation loop occurs.
    """
    assistant_prompt = "Hello Arthur! It is wonderful to speak with you today. How are you feeling this morning?"
    history = [
        {"role": "assistant", "content": assistant_prompt}
    ]

    # Microphone echoes back Elena's own greeting
    echoed_text = "Hello Arthur it is wonderful to speak with you today how are you feeling this morning"

    res = await voice_orchestrator.process_turn(
        db=db_session,
        user_id=senior_user.id,
        text_input=echoed_text,
        history=history,
        context_state="wellness_check"
    )

    assert res["echo_rejected"] is True
    assert res["assistant_text"] == ""
    assert res["audio_base64"] == ""
    assert res["intent"] == "echo_ignored"


@pytest.mark.asyncio
async def test_genuine_user_speech_is_accepted_after_assistant_speech(db_session, senior_user):
    """
    Verify that genuine user speech (different from assistant speech) is processed normally.
    """
    assistant_prompt = "Hello Arthur! It is wonderful to speak with you today. How are you feeling this morning?"
    history = [
        {"role": "assistant", "content": assistant_prompt}
    ]

    user_text = "I am feeling wonderful today, thank you."

    res = await voice_orchestrator.process_turn(
        db=db_session,
        user_id=senior_user.id,
        text_input=user_text,
        history=history,
        context_state="wellness_check"
    )

    assert res.get("echo_rejected", False) is False
    assert res["user_text"] == user_text
    assert len(res["assistant_text"]) > 0


@pytest.mark.asyncio
async def test_turn_fencing_rejects_stale_in_flight_turns(db_session, senior_user):
    """
    Verify that if a senior interrupts and starts a new turn while an older turn
    was in-flight, the older turn is rejected as stale.
    """
    store = TurnStateStore()
    old_turn_id = "turn_101"
    new_turn_id = "turn_102"

    store.register_turn(senior_user.id, old_turn_id)
    # User interrupts and new turn begins
    store.register_turn(senior_user.id, new_turn_id)

    # Verify old turn is marked stale
    assert store.is_active_turn(senior_user.id, old_turn_id) is False
    assert store.is_active_turn(senior_user.id, new_turn_id) is True

    # Process old turn -> should return stale: True
    with patch("app.services.voice_orchestrator.turn_state_store", store):
        res = await voice_orchestrator.process_turn(
            db=db_session,
            user_id=senior_user.id,
            text_input="Old message",
            turn_id=old_turn_id
        )
        assert res["stale"] is True
        assert res["assistant_text"] == ""


@pytest.mark.asyncio
async def test_interruption_during_assistant_speaking_creates_clean_new_turn(db_session, senior_user):
    """
    Verify that when user interrupts with 'Wait, stop', a new active turn is created.
    """
    history = [
        {"role": "assistant", "content": "I am checking your daily blood pressure report and the numbers look..."}
    ]
    interrupt_text = "Wait stop Elena, I need to tell you something first."

    res = await voice_orchestrator.process_turn(
        db=db_session,
        user_id=senior_user.id,
        text_input=interrupt_text,
        history=history,
        turn_id="turn_interrupt_001"
    )

    assert res["stale"] is False
    assert res.get("echo_rejected", False) is False
    assert res["user_text"] == interrupt_text
    assert len(res["assistant_text"]) > 0
