import pytest
from app.services.voice_nlp import voice_nlp, IntentClassificationResult


def test_normalization_and_contraction_expansion():
    text = "  Well... um, I didn't take my medicine yet, you know?  "
    norm = voice_nlp.normalize_text(text)
    assert "did not" in norm
    assert "well" not in norm.split()
    assert "um" not in norm.split()
    assert "you know" not in norm
    assert "not" in norm  # Explicit negation preservation


def test_negation_preservation():
    # Crucial rule: Negations must NEVER be stripped
    text = "I am not feeling well at all"
    tokens = voice_nlp.tokenize_without_stripping_negations(text)
    assert "not" in tokens
    assert "well" in tokens
    assert "feeling" in tokens

    text2 = "I have never felt this dizzy before"
    tokens2 = voice_nlp.tokenize_without_stripping_negations(text2)
    assert "never" in tokens2


def test_urgent_symptom_detection():
    # Emergency phrases must always be detected
    urgent_cases = [
        "I have severe chest pain and cannot breathe",
        "I fell down in the bathroom and can't get up",
        "I took too many pills by mistake",
        "There is blood coming from my wound",
        "I feel like passing out and having a stroke",
    ]
    for phrase in urgent_cases:
        is_urgent, reasons = voice_nlp.detect_urgent_symptoms(phrase)
        assert is_urgent is True
        assert len(reasons) > 0

    # Non-urgent phrases must NOT trigger false alarms
    non_urgent = [
        "I'm feeling good today",
        "I took my morning pills with water",
        "I had a nice breakfast",
        "My left knee has a mild ache",
    ]
    for phrase in non_urgent:
        is_urgent, reasons = voice_nlp.detect_urgent_symptoms(phrase)
        assert is_urgent is False


def test_intent_classification_wellness_check():
    res_pos = voice_nlp.classify_intent("I am feeling great this morning", context_state="wellness_check")
    assert res_pos.intent == "mood_positive"
    assert res_pos.confidence >= 0.7

    res_neg = voice_nlp.classify_intent("I am not feeling very well today", context_state="wellness_check")
    assert res_neg.intent == "mood_low"
    assert res_neg.confidence >= 0.7

    res_neutral = voice_nlp.classify_intent("I am doing okay today, nothing new", context_state="wellness_check")
    assert res_neutral.intent == "mood_normal"


def test_intent_classification_medication_check():
    res_taken = voice_nlp.classify_intent("Yes I took my morning blood pressure pills", context_state="medication_check")
    assert res_taken.intent == "medication_taken"
    assert res_taken.confidence >= 0.7

    res_missed = voice_nlp.classify_intent("No I forgot to take my pills today", context_state="medication_check")
    assert res_missed.intent == "medication_missed"
    assert res_missed.confidence >= 0.7


def test_intent_classification_sleep_and_pain():
    res_sleep_good = voice_nlp.classify_intent("I slept like a baby last night", context_state="sleep_inquiry")
    assert res_sleep_good.intent == "sleep_good"

    res_sleep_bad = voice_nlp.classify_intent("Barely slept at all, insomnia was bad", context_state="sleep_inquiry")
    assert res_sleep_bad.intent == "sleep_poor"

    res_pain_none = voice_nlp.classify_intent("No pain anywhere today", context_state="pain_check")
    assert res_pain_none.intent == "pain_none"
