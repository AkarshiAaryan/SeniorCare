import pytest
from app.services.voice_intent_predictor import voice_intent_predictor


def test_infer_conversational_state():
    # Test inferring state from assistant utterances
    u1 = "Good morning John, how are you feeling today?"
    assert voice_intent_predictor.infer_conversational_state(u1) == "wellness_check"

    u2 = "It's 9 AM, did you get a chance to take your heart medicine?"
    assert voice_intent_predictor.infer_conversational_state(u2) == "medication_check"

    u3 = "Did you get a good night's sleep?"
    assert voice_intent_predictor.infer_conversational_state(u3) == "sleep_inquiry"

    u4 = "Are you experiencing any physical pain or discomfort right now?"
    assert voice_intent_predictor.infer_conversational_state(u4) == "pain_check"

    u5 = "How has your appetite been today?"
    assert voice_intent_predictor.infer_conversational_state(u5) == "appetite_check"

    u6 = "Is there anything else on your mind today?"
    assert voice_intent_predictor.infer_conversational_state(u6) == "general_followup"


def test_predict_top_k_intents():
    # Wellness check top predictions
    preds_wellness = voice_intent_predictor.predict_top_k_intents("wellness_check", k=2)
    assert len(preds_wellness) == 2
    intents = [p[0] for p in preds_wellness]
    assert "mood_positive" in intents
    assert "mood_normal" in intents
    assert preds_wellness[0][1] >= preds_wellness[1][1]  # Ranked by probability

    # Medication check top predictions
    preds_med = voice_intent_predictor.predict_top_k_intents("medication_check", k=2)
    assert len(preds_med) == 2
    med_intents = [p[0] for p in preds_med]
    assert "medication_taken" in med_intents
    assert "medication_missed" in med_intents


def test_state_transitions():
    next_state = voice_intent_predictor.get_next_likely_state("wellness_check", "mood_positive")
    assert next_state in ["medication_check", "general_followup", "sleep_inquiry"]
