"""
Voice Intent Predictor Module for SeniorCare
Predicts the top-K most likely user response intents based on conversational state and context.
"""

import logging
from typing import List, Tuple, Dict, Optional, Any
from app.config import settings

logger = logging.getLogger("VoiceIntentPredictor")

# Context state intent probability distributions
CONTEXT_INTENT_DISTRIBUTIONS: Dict[str, Dict[str, float]] = {
    "wellness_check": {
        "mood_positive": 0.40,
        "mood_normal": 0.25,
        "mood_tired": 0.15,
        "mood_low": 0.10,
        "pain_present": 0.05,
        "unknown": 0.05,
    },
    "sleep_inquiry": {
        "sleep_good": 0.50,
        "sleep_poor": 0.30,
        "sleep_interrupted": 0.15,
        "insomnia": 0.05,
    },
    "medication_check": {
        "medication_taken": 0.65,
        "medication_missed": 0.25,
        "medication_uncertain": 0.10,
    },
    "pain_check": {
        "pain_none": 0.55,
        "pain_present": 0.35,
        "pain_severe": 0.10,
    },
    "emotion_check": {
        "mood_positive": 0.40,
        "mood_low": 0.30,
        "mood_lonely": 0.20,
        "mood_anxious": 0.10,
    },
    "appetite_check": {
        "appetite_good": 0.60,
        "appetite_poor": 0.40,
    },
    "general_followup": {
        "conversation_close": 0.60,
        "mood_low": 0.20,
        "pain_present": 0.20,
    }
}


class VoiceIntentPredictorService:
    def __init__(self, default_top_k: int = 2):
        self.default_top_k = default_top_k

    def infer_conversational_state(
        self,
        assistant_text: Any,
        history: Optional[List[dict]] = None
    ) -> str:
        """
        Infers the conversational state/question type from Elena's latest speech prompt.
        """
        if isinstance(assistant_text, dict):
            assistant_text = assistant_text.get("text", "") or assistant_text.get("content", "")

        if not assistant_text or not isinstance(assistant_text, str):
            return "wellness_check"

        text_lower = assistant_text.lower()

        if any(w in text_lower for w in ["medicine", "pill", "pills", "dose", "medication", "prescribed", "lisinopril", "metformin"]):
            return "medication_check"

        if any(w in text_lower for w in ["sleep", "slept", "rested", "night", "insomnia"]):
            return "sleep_inquiry"

        if any(w in text_lower for w in ["pain", "hurt", "aching", "sore", "knee", "back", "comfortable"]):
            return "pain_check"

        if any(w in text_lower for w in ["appetite", "eat", "eaten", "breakfast", "lunch", "dinner", "meal"]):
            return "appetite_check"

        if any(w in text_lower for w in ["lonely", "emotionally", "sad", "feeling down", "cheer"]):
            return "emotion_check"

        if any(w in text_lower for w in ["anything else", "on your mind", "chat about", "share today"]):
            return "general_followup"

        return "wellness_check"

    def predict_top_k_intents(
        self,
        context_state: str,
        k: Optional[int] = None
    ) -> List[Tuple[str, float]]:
        """
        Returns the top K predicted user intents and their prior probabilities
        for a given conversational state.
        """
        top_k = k if k is not None else getattr(settings, "PREFETCH_TOP_K", self.default_top_k)
        top_k = max(1, top_k)

        dist = CONTEXT_INTENT_DISTRIBUTIONS.get(context_state, CONTEXT_INTENT_DISTRIBUTIONS["wellness_check"])
        sorted_intents = sorted(dist.items(), key=lambda x: x[1], reverse=True)

        return sorted_intents[:top_k]

    def get_supported_states(self) -> List[str]:
        """
        Returns list of all supported conversational context states.
        """
        return list(CONTEXT_INTENT_DISTRIBUTIONS.keys())

    def get_next_likely_state(self, current_state: str, current_intent: str) -> str:
        """
        Infers next likely conversational state given current state and intent.
        """
        transitions = {
            "wellness_check": "medication_check",
            "medication_check": "sleep_inquiry",
            "sleep_inquiry": "pain_check",
            "pain_check": "general_followup",
            "emotion_check": "general_followup",
            "appetite_check": "general_followup",
            "general_followup": "wellness_check"
        }
        return transitions.get(current_state, "general_followup")


voice_intent_predictor = VoiceIntentPredictorService()
