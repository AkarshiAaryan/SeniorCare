"""
Voice NLP Module for SeniorCare
Fast, lightweight, negation-aware intent detection and normalization pipeline.
Maps spoken user utterances to canonical clinical and conversational intents.
"""

import re
import logging
from dataclasses import dataclass
from typing import Optional, List, Dict, Tuple

logger = logging.getLogger("VoiceNLP")


@dataclass
class IntentClassificationResult:
    intent: str
    confidence: float
    normalized_text: str
    is_urgent: bool = False
    matched_pattern: Optional[str] = None
    detected_entities: Optional[Dict[str, str]] = None


# Contraction expansion dictionary
CONTRACTION_MAP = {
    r"\bi'm\b": "i am",
    r"\bi've\b": "i have",
    r"\bi'll\b": "i will",
    r"\bi'd\b": "i would",
    r"\bdon't\b": "do not",
    r"\bdont\b": "do not",
    r"\bdidn't\b": "did not",
    r"\bdidnt\b": "did not",
    r"\bcan't\b": "cannot",
    r"\bcant\b": "cannot",
    r"\bwon't\b": "will not",
    r"\bwont\b": "will not",
    r"\bisn't\b": "is not",
    r"\bisnt\b": "is not",
    r"\baren't\b": "are not",
    r"\barent\b": "are not",
    r"\bwasn't\b": "was not",
    r"\bwasnt\b": "was not",
    r"\bweren't\b": "were not",
    r"\bwerent\b": "were not",
    r"\bhaven't\b": "have not",
    r"\bhavent\b": "have not",
    r"\bhasn't\b": "has not",
    r"\bhasnt\b": "has not",
    r"\bhadn't\b": "had not",
    r"\bhadnt\b": "had not",
    r"\bit's\b": "it is",
    r"\bthat's\b": "that is",
    r"\bthere's\b": "there is",
    r"\byou're\b": "you are",
    r"\bwe're\b": "we are",
    r"\bthey're\b": "they are",
    r"\bain't\b": "is not",
}

# Filler patterns (at starts of sentences or isolated pauses)
FILLER_PATTERNS = [
    r"^(um+|uh+|er+|ah+|like|you know|well|oh)\b[,.\s]*",
    r"\b(um+|uh+|er+|ah+|you know)\b",
]

# Urgent red flag symptom patterns
URGENT_PATTERNS = [
    (r"\b(severe|sharp|crushing|heavy|tight|bad)\s+(chest\s+pain|chest|heart)\b", "severe_chest_pain"),
    (r"\b(cannot|can't|can not|hard to|trouble|struggling to)\s+(breathe|breathing)\b", "respiratory_distress"),
    (r"\bshortness\s+of\s+breath\b", "shortness_of_breath"),
    (r"\b(fell\s+down|had\s+a\s+fall|collapsed|passed\s+out|fainted|blacked\s+out|cannot\s+get\s+up)\b", "fall_or_collapse"),
    (r"\b(took\s+too\s+many|overdose|too\s+many\s+pills|extra\s+pills|wrong\s+pills)\b", "medication_overdose"),
    (r"\b(bleeding\s+heavily|bleeding|blood\s+coming|coughing\s+blood|throwing\s+up\s+blood|blood\s+in\s+stool)\b", "acute_bleeding"),
    (r"\b(stroke|face\s+droop|arm\s+numb|slurred\s+speech|cannot\s+move\s+arm)\b", "stroke_signs"),
    (r"\b(emergency|call\s+911|need\s+an\s+ambulance|take\s+me\s+to\s+hospital)\b", "emergency_call"),
]

# Negation terms (must NEVER be stripped as stopwords)
NEGATION_REGEX = re.compile(r"\b(not|no|never|hardly|barely|without|neither|nor|none|cannot)\b", re.IGNORECASE)


class VoiceNLPService:
    def normalize_transcript(self, text: str) -> str:
        """
        Normalizes spoken transcript:
        1. Lowercases and cleans whitespace.
        2. Expands contractions (e.g. "I'm" -> "i am", "didn't" -> "did not").
        3. Strips conversational fillers (e.g. "um", "uh") while PRESERVING all negation words.
        4. Removes non-semantic punctuation.
        """
        if not text:
            return ""

        cleaned = text.lower().strip()

        # 1. Expand contractions
        for pattern, replacement in CONTRACTION_MAP.items():
            cleaned = re.sub(pattern, replacement, cleaned, flags=re.IGNORECASE)

        # 2. Strip fillers
        for pat in FILLER_PATTERNS:
            cleaned = re.sub(pat, "", cleaned, flags=re.IGNORECASE)

        # 3. Clean punctuation (keep alphanumeric, spaces, and negation tokens)
        cleaned = re.sub(r"[^\w\s]", " ", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()

        return cleaned

    def normalize_text(self, text: str) -> str:
        return self.normalize_transcript(text)

    def tokenize_without_stripping_negations(self, text: str) -> List[str]:
        norm = self.normalize_transcript(text)
        return norm.split()

    def detect_urgent_symptoms(self, text: str) -> Tuple[bool, Optional[str]]:
        """
        Scans for high-risk red-flag symptoms. Returns (is_urgent, symptom_type).
        """
        normalized = self.normalize_transcript(text)
        for pattern, symptom_name in URGENT_PATTERNS:
            if re.search(pattern, normalized, re.IGNORECASE):
                return True, symptom_name
        return False, None

    def has_negation(self, text: str) -> bool:
        """
        Checks if text contains explicit negation tokens.
        """
        return bool(NEGATION_REGEX.search(text))

    def classify_intent(
        self,
        transcript: str,
        context_state: Optional[str] = None
    ) -> IntentClassificationResult:
        """
        Negation-aware, context-guided intent classification.
        Maps the user transcript to canonical intents with a confidence score.
        """
        if not transcript or not transcript.strip():
            return IntentClassificationResult(
                intent="unknown",
                confidence=0.0,
                normalized_text=""
            )

        normalized = self.normalize_transcript(transcript)

        # 1. First Priority: Safety & Urgent Symptom Detection
        is_urgent, urgent_symptom = self.detect_urgent_symptoms(normalized)
        if is_urgent:
            return IntentClassificationResult(
                intent="urgent_symptom",
                confidence=1.0,
                normalized_text=normalized,
                is_urgent=True,
                matched_pattern=urgent_symptom,
                detected_entities={"symptom": urgent_symptom or "urgent"}
            )

        neg = self.has_negation(normalized)

        # 2. Context-Specific High Priority Intent Resolvers

        # A. Medication Check Context
        if context_state == "medication_check":
            if (
                not neg
                and any(w in normalized for w in ["yes", "took", "taken", "already", "did take", "all done", "have taken"])
                and any(w in normalized for w in ["it", "medicine", "pill", "pills", "dose", "them", "morning", "night", "yes"])
            ) or normalized in ["yes", "yes i did", "i took it", "i took them", "already took it", "took my medicine", "all taken"]:
                return IntentClassificationResult("medication_taken", 0.95, normalized, matched_pattern="medication_taken_confirmed")

            if neg and any(w in normalized for w in ["take", "taken", "forget", "forgot", "yet", "have not", "did not", "missed", "no"]):
                return IntentClassificationResult("medication_missed", 0.95, normalized, matched_pattern="medication_missed_confirmed")

            if any(w in normalized for w in ["not sure", "cannot remember", "do not remember", "maybe"]):
                return IntentClassificationResult("medication_uncertain", 0.90, normalized, matched_pattern="medication_uncertain")

        # B. Sleep Inquiry Context
        if context_state == "sleep_inquiry":
            if (
                not neg
                and any(w in normalized for w in ["slept well", "good sleep", "slept great", "slept fine", "very well", "like a baby", "great sleep", "soundly", "rested"])
            ) or (not neg and normalized in ["good", "well", "great", "fine", "very well", "yes", "i did"]):
                return IntentClassificationResult("sleep_good", 0.95, normalized, matched_pattern="sleep_good_confirmed")

            if (
                (neg and any(w in normalized for w in ["well", "good", "great", "fine", "rest", "sleep"]))
                or any(w in normalized for w in ["hardly slept", "barely slept", "bad sleep", "poor sleep", "terrible sleep", "tossed and turned", "restless", "trouble sleeping", "could not sleep", "no sleep"])
            ):
                return IntentClassificationResult("sleep_poor", 0.95, normalized, matched_pattern="sleep_poor_confirmed")

            if any(w in normalized for w in ["woke up several times", "interrupted", "kept waking up", "woke up in the middle"]):
                return IntentClassificationResult("sleep_interrupted", 0.90, normalized, matched_pattern="sleep_interrupted")

            if "insomnia" in normalized or "awake all night" in normalized:
                return IntentClassificationResult("insomnia", 0.90, normalized, matched_pattern="insomnia")

        # C. Pain Check Context
        if context_state == "pain_check":
            if (
                (neg and any(w in normalized for w in ["pain", "hurt", "hurts", "ache", "aching", "sore"]))
                or any(w in normalized for w in ["no pain", "pain free", "not hurting", "does not hurt", "none at all", "feeling good", "no"])
            ):
                return IntentClassificationResult("pain_none", 0.95, normalized, matched_pattern="pain_none_confirmed")

            if any(w in normalized for w in ["severe", "terrible", "unbearable", "horrible", "intense"]) and any(w in normalized for w in ["pain", "hurt", "ache"]):
                return IntentClassificationResult("pain_severe", 0.95, normalized, matched_pattern="pain_severe")

            for loc in ["knee", "back", "head", "headache", "shoulder", "hip", "neck", "stomach", "leg", "arm", "joint"]:
                if loc in normalized and any(w in normalized for w in ["pain", "hurt", "hurts", "ache", "aching", "sore"]):
                    return IntentClassificationResult("pain_location_specific", 0.90, normalized, matched_pattern=f"pain_location_{loc}", detected_entities={"location": loc})

            if any(w in normalized for w in ["pain", "hurt", "hurts", "ache", "aching", "sore", "a bit"]):
                return IntentClassificationResult("pain_present", 0.90, normalized, matched_pattern="pain_present")

        # D. Appetite Check Context
        if context_state == "appetite_check":
            if (
                not neg
                and any(w in normalized for w in ["ate well", "good appetite", "eating fine", "hungry", "finished my meal", "had breakfast", "had lunch", "had dinner", "good", "yes"])
            ):
                return IntentClassificationResult("appetite_good", 0.95, normalized, matched_pattern="appetite_good")

            if (
                (neg and any(w in normalized for w in ["hungry", "appetite", "eat", "eating"]))
                or any(w in normalized for w in ["no appetite", "lost my appetite", "cannot eat", "did not eat", "nauseous", "queasy"])
            ):
                return IntentClassificationResult("appetite_poor", 0.95, normalized, matched_pattern="appetite_poor")

        # 3. Global Intent Matching (Applies to all contexts, including wellness_check & emotion_check)

        # Medication check intents (when mentioned directly)
        if any(w in normalized for w in ["pill", "pills", "medication", "medicine"]):
            if neg or any(w in normalized for w in ["forgot", "missed", "not yet", "have not"]):
                return IntentClassificationResult("medication_missed", 0.95, normalized, matched_pattern="global_medication_missed")
            if any(w in normalized for w in ["took", "taken", "already", "yes"]):
                return IntentClassificationResult("medication_taken", 0.95, normalized, matched_pattern="global_medication_taken")

        # Sleep check intents (when mentioned directly)
        if any(w in normalized for w in ["sleep", "slept", "insomnia"]):
            if (
                (neg and any(w in normalized for w in ["well", "good", "great", "fine", "much"]))
                or any(w in normalized for w in ["poorly", "bad", "terrible", "hardly", "barely", "tossed"])
            ):
                return IntentClassificationResult("sleep_poor", 0.95, normalized, matched_pattern="global_sleep_poor")
            if not neg and any(w in normalized for w in ["well", "good", "great", "fine", "rested", "soundly"]):
                return IntentClassificationResult("sleep_good", 0.95, normalized, matched_pattern="global_sleep_good")

        # Pain check intents (when mentioned directly)
        if (
            (neg and any(w in normalized for w in ["pain", "hurt", "ache", "sore"]))
            or any(w in normalized for w in ["no pain", "pain free", "not hurting", "does not hurt", "none"])
        ) and any(w in normalized for w in ["pain", "hurt", "ache"]):
            return IntentClassificationResult("pain_none", 0.95, normalized, matched_pattern="global_pain_none")

        if any(w in normalized for w in ["pain", "hurt", "hurts", "hurting", "sore", "aching", "ache"]):
            if any(w in normalized for w in ["severe", "terrible", "unbearable", "horrible"]):
                return IntentClassificationResult("pain_severe", 0.95, normalized, matched_pattern="global_pain_severe")
            for loc in ["knee", "back", "head", "headache", "shoulder", "hip", "neck", "stomach", "leg", "arm"]:
                if loc in normalized:
                    return IntentClassificationResult("pain_location_specific", 0.90, normalized, matched_pattern=f"global_pain_{loc}", detected_entities={"location": loc})
            return IntentClassificationResult("pain_present", 0.90, normalized, matched_pattern="global_pain_present")

        # Emotional & Mood Intents (with strict negation awareness)
        if (
            (neg and any(w in normalized for w in ["well", "good", "great", "fine", "better", "alright", "happy"]))
            or any(w in normalized for w in ["down", "sad", "depressed", "blue", "unhappy", "crying", "miserable", "terrible", "awful", "bad day", "feel low", "feeling low", "feel down", "feeling down"])
        ):
            return IntentClassificationResult("mood_low", 0.95, normalized, matched_pattern="mood_low_detected")

        if any(w in normalized for w in ["lonely", "alone", "isolated", "miss everyone"]):
            return IntentClassificationResult("mood_lonely", 0.95, normalized, matched_pattern="mood_lonely_detected")

        if any(w in normalized for w in ["anxious", "worried", "nervous", "scared", "fear", "panic"]):
            return IntentClassificationResult("mood_anxious", 0.90, normalized, matched_pattern="mood_anxious_detected")

        if (
            not (neg and "tired" in normalized)
            and any(w in normalized for w in ["tired", "exhausted", "fatigued", "sleepy", "drowsy", "worn out", "no energy"])
        ):
            return IntentClassificationResult("mood_tired", 0.90, normalized, matched_pattern="mood_tired_detected")

        # Positive & Normal Moods (ONLY when NO negation is present!)
        if not neg:
            if any(w in normalized for w in ["good", "great", "well", "fine", "wonderful", "fantastic", "cheerful", "happy", "better", "all good", "doing good", "doing well"]):
                return IntentClassificationResult("mood_positive", 0.95, normalized, matched_pattern="mood_positive_detected")

            if any(w in normalized for w in ["okay", "alright", "so so", "hanging in", "about the same", "not bad"]):
                return IntentClassificationResult("mood_normal", 0.90, normalized, matched_pattern="mood_normal_detected")

        # General Conversational Close
        if normalized.startswith("no") and (
            len(normalized) < 20
            or any(w in normalized for w in ["nothing", "else", "all good", "all set", "that is all", "bye", "goodbye"])
        ):
            return IntentClassificationResult("conversation_close", 0.95, normalized, matched_pattern="conversation_close")

        # Fallback / Unknown
        return IntentClassificationResult(
            intent="unknown",
            confidence=0.3,
            normalized_text=normalized
        )


voice_nlp = VoiceNLPService()
