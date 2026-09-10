"""
Voice Response Store Module for SeniorCare
Centralized registry for canonical prefetch response templates mapped to (context_state, intent).
"""

import logging
from typing import Dict, Tuple, Optional

logger = logging.getLogger("VoiceResponseStore")

# Default canonical response templates
# Mapping: (context_state, intent) -> template string
DEFAULT_CANONICAL_RESPONSES: Dict[Tuple[str, str], str] = {
    # Wellness Check Context
    ("wellness_check", "mood_positive"): (
        "I am so glad to hear you are doing well, {user_name}! Have you had a chance to take your prescribed medicine today?"
    ),
    ("wellness_check", "mood_normal"): (
        "That is good to hear, {user_name}. Is there anything specific on your mind today?"
    ),
    ("wellness_check", "mood_low"): (
        "I am so sorry you are feeling down today, {user_name}. Please know I am right here with you. What is on your mind?"
    ),
    ("wellness_check", "mood_tired"): (
        "I understand, {user_name}. Getting good rest is so important. How did you sleep last night?"
    ),
    ("wellness_check", "mood_anxious"): (
        "I am right here with you, {user_name}. Take a gentle breath. Would you like to tell me what is worrying you?"
    ),
    ("wellness_check", "mood_lonely"): (
        "I am right here chatting with you, {user_name}. I always enjoy our conversations. What is on your mind today?"
    ),
    ("wellness_check", "pain_present"): (
        "I am sorry to hear you are in pain, {user_name}. Please take it easy and rest. Have you taken your prescribed medicine today?"
    ),

    # Sleep Inquiry Context
    ("sleep_inquiry", "sleep_good"): (
        "Wonderful news, {user_name}! A good night of sleep makes all the difference. How are you feeling this morning?"
    ),
    ("sleep_inquiry", "sleep_poor"): (
        "I am so sorry you did not sleep well, {user_name}. Please take it easy today and make sure to rest comfortably."
    ),
    ("sleep_inquiry", "sleep_interrupted"): (
        "I understand, {user_name}. Waking up during the night can be tiring. Please take time to relax and rest today."
    ),
    ("sleep_inquiry", "insomnia"): (
        "I am sorry you had trouble sleeping, {user_name}. Resting quietly is still helpful. Would you like to chat a bit?"
    ),

    # Medication Check Context
    ("medication_check", "medication_taken"): (
        "Wonderful, {user_name}! Thank you for staying on track with your medicine. How did you sleep last night?"
    ),
    ("medication_check", "medication_missed"): (
        "I understand, {user_name}. Please take your prescribed dose when you are ready, or let your caregiver know if you need help."
    ),
    ("medication_check", "medication_uncertain"): (
        "No problem, {user_name}. It is a good idea to check your pill organizer when you get a moment."
    ),

    # Pain Check Context
    ("pain_check", "pain_none"): (
        "That is wonderful news, {user_name}! I am glad you are comfortable and pain free today."
    ),
    ("pain_check", "pain_present"): (
        "I am sorry you are experiencing pain, {user_name}. Please sit comfortably and rest. Would you like me to notify your caregiver?"
    ),
    ("pain_check", "pain_severe"): (
        "I am so sorry to hear that, {user_name}. If your pain is severe, please rest and let us notify your caregiver or doctor right away."
    ),
    ("pain_check", "pain_location_specific"): (
        "I am sorry your {location} is hurting, {user_name}. Please take it easy and avoid straining yourself."
    ),

    # Emotion Check Context
    ("emotion_check", "mood_positive"): (
        "That brings a smile to my face, {user_name}! I am so happy you are feeling good today."
    ),
    ("emotion_check", "mood_low"): (
        "I am so sorry you are feeling down, {user_name}. You are never alone. Tell me what is on your heart."
    ),
    ("emotion_check", "mood_lonely"): (
        "I am right here with you, {user_name}. Remember that your caregivers and I care about you deeply."
    ),
    ("emotion_check", "mood_anxious"): (
        "Please take it slow, {user_name}. You are safe here. Would you like to tell me what is troubling you?"
    ),

    # Appetite Check Context
    ("appetite_check", "appetite_good"): (
        "That is great news, {user_name}! Eating well is so important for keeping your energy and strength up."
    ),
    ("appetite_check", "appetite_poor"): (
        "I understand, {user_name}. Try sipping some water or having a light snack whenever you feel ready."
    ),

    # General Followup Context
    ("general_followup", "conversation_close"): (
        "Alright, {user_name}! Thank you for chatting with me today. Have a lovely day, and remember I am always here for you."
    ),
    ("general_followup", "mood_low"): (
        "Thank you for sharing that with me, {user_name}. Please know I am always here to listen and support you."
    ),
    ("general_followup", "pain_present"): (
        "Thank you for letting me know, {user_name}. Please take good care of yourself and rest."
    ),

    # Proactive Precomputed Greetings
    ("proactive_greeting", "initial_greeting"): (
        "Hello {user_name}! I am Elena, your voice care assistant. How are you feeling today?"
    ),
    ("proactive_greeting", "3_hour_checkin"): (
        "Hello {user_name}! Elena here for your check-in. How are you feeling right now?"
    ),
    ("proactive_greeting", "medication_due"): (
        "Hello {user_name}! Elena here with a quick reminder for your scheduled medicine. Have you taken your dose yet?"
    )
}


class VoiceResponseStoreService:
    def __init__(self):
        self.responses: Dict[Tuple[str, str], str] = dict(DEFAULT_CANONICAL_RESPONSES)

    def get_canonical_response(
        self,
        context_state: str,
        intent: str,
        user_name: str = "Friend",
        **kwargs
    ) -> Optional[str]:
        """
        Retrieves and renders the canonical assistant response template for (context_state, intent).
        """
        template = self.responses.get((context_state, intent))
        if not template:
            # Fallback to generic wellness template if available
            template = self.responses.get(("wellness_check", intent))

        if not template:
            return None

        # Format template with variables
        template_vars = {"user_name": user_name, "location": kwargs.get("location", "body")}
        template_vars.update(kwargs)

        try:
            return template.format(**template_vars)
        except Exception as e:
            logger.warning(f"Error formatting response template for ({context_state}, {intent}): {e}")
            return template.replace("{user_name}", user_name)

    def register_canonical_response(
        self,
        context_state: str,
        intent: str,
        template: str
    ) -> None:
        """
        Registers or overrides a canonical response template.
        """
        self.responses[(context_state, intent)] = template

    def get_response_id(self, context_state: str, intent: str) -> str:
        """
        Returns unique canonical response ID.
        """
        return f"{context_state}__{intent}"

    def list_all_keys(self):
        """
        Returns all registered (context_state, intent) keys.
        """
        return list(self.responses.keys())


voice_response_store = VoiceResponseStoreService()
