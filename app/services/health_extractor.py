import json
import logging
import httpx
from typing import Dict, Any, List, Optional
from app.config import settings

logger = logging.getLogger("HealthExtractor")

EXTRACTION_SYSTEM_PROMPT = """You are a clinical data extraction assistant.
Analyze the conversation transcript between an elderly senior and a care assistant.
Extract structured health metrics and medication intake details into a valid JSON object matching this schema:

{
  "mood": "string (e.g. good, normal, tired, anxious, low, not reported)",
  "sleep": "string (e.g. good, normal, poor, interrupted, not reported)",
  "appetite": "string (e.g. good, normal, poor, low, not reported)",
  "pain": "string (e.g. none reported, mild knee pain, back pain, headache)",
  "medication_taken": boolean or null,
  "medications": [
    {
      "name": "string",
      "taken": true/false,
      "scheduled_time": "HH:MM (if mentioned, otherwise null)"
    }
  ],
  "urgent_alert": boolean,
  "summary_note": "Brief 1-sentence clinician summary"
}

Output only raw JSON without backticks or markdown formatting.
"""


def is_valid_key(key: str) -> bool:
    return bool(key and key.strip() and not key.startswith("your_"))


class HealthExtractorService:
    def __init__(self):
        self.gemini_key = settings.GEMINI_API_KEY
        self.gemini_model = settings.GEMINI_MODEL
        self.openai_key = settings.OPENAI_API_KEY
        self.groq_key = settings.GROQ_API_KEY

    def _fallback_result(self, transcript: str, known_medications: Optional[List[str]]=None) -> Dict[str, Any]:
        text_lower = transcript.lower()

        mood = "normal"
        if any(w in text_lower for w in ["happy", "great", "cheerful", "good"]):
            mood = "good"
        elif any(w in text_lower for w in ["sad", "depressed", "lonely"]):
            mood = "sad"
        elif any(w in text_lower for w in ["tired", "exhausted", "sleepy", "drowsy"]):
            mood = "tired"
        elif any(w in text_lower for w in ["anxious", "worried", "nervous"]):
            mood = "anxious"

        sleep = "normal"
        if any(w in text_lower for w in ["slept poorly", "poor sleep", "didn't sleep", "insomnia", "bad sleep", "trouble sleeping"]):
            sleep = "poor"
        elif any(w in text_lower for w in ["slept well", "good sleep", "slept great"]):
            sleep = "good"

        appetite = "normal"
        if any(w in text_lower for w in ["no appetite", "not hungry", "haven't eaten", "poor appetite", "eating less"]):
            appetite = "poor"
        elif any(w in text_lower for w in ["good appetite", "ate well", "hungry"]):
            appetite = "good"

        pain = "none reported"
        if "knee" in text_lower and ("pain" in text_lower or "hurt" in text_lower or "ache" in text_lower):
            pain = "mild knee pain"
        elif "headache" in text_lower:
            pain = "headache"
        elif "back" in text_lower and ("pain" in text_lower or "hurt" in text_lower or "ache" in text_lower):
            pain = "back pain"
        elif "pain" in text_lower or "hurts" in text_lower:
            pain = "reported pain"

        med_taken = None
        import re
        if re.search(r'\b(took|taken)\s+(my\s+)?(morning\s+|evening\s+|night\s+|daily\s+)?(medicine|pill|medicines|pills|medication|dose|tablet|tablets|it)\b', text_lower):
            med_taken = True
        elif re.search(r'\b(didn\'t|did not|forgot to|haven\'t|have not|missed)\s+(take|taken)?\s*(my\s+)?(morning\s+|evening\s+|night\s+)?(medicine|pill|medicines|pills|medication|dose)\b', text_lower):
            med_taken = False

        meds_list = []
        if known_medications:
            for km in known_medications:
                if km.lower() in text_lower:
                    meds_list.append({"name": km, "taken": med_taken if med_taken is not None else True, "scheduled_time": "08:00"})

        urgent = any(w in text_lower for w in ["chest pain", "fell down", "can't breathe", "emergency", "fainted"])

        return {
            "mood": mood,
            "sleep": sleep,
            "appetite": appetite,
            "pain": pain,
            "medication_taken": med_taken,
            "medications": meds_list,
            "urgent_alert": urgent,
            "summary_note": f"User reported {mood} mood, {sleep} sleep, and {pain}."
        }

    async def extract_from_transcript(self, transcript: str, known_medications: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Extract structured health status and medication adherence from dialogue text.
        """
        if not transcript or not transcript.strip():
            return {
                "mood": "not reported",
                "sleep": "not reported",
                "appetite": "not reported",
                "pain": "none reported",
                "medication_taken": None,
                "medications": [],
                "urgent_alert": False,
                "summary_note": "No conversation data."
            }

        prompt_user = f"Known medications: {known_medications or []}\n\nTranscript:\n{transcript}"

        # 1. Try Gemini API JSON extraction (Native Google REST Endpoint)
        if is_valid_key(self.gemini_key):
            candidate_models = [self.gemini_model, "gemini-2.5-flash-lite", "gemini-flash-latest", "gemini-2.5-flash"]
            seen_models = set()
            models_to_try = [m for m in candidate_models if m and not (m in seen_models or seen_models.add(m))]
            payload = {
                "systemInstruction": {
                    "parts": [{"text": EXTRACTION_SYSTEM_PROMPT}]
                },
                "contents": [{
                    "role": "user",
                    "parts": [{"text": prompt_user}]
                }],
                "generationConfig": {
                    "responseMimeType": "application/json",
                    "temperature": 0.1
                }
            }
            for model_name in models_to_try:
                try:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={self.gemini_key}"
                    async with httpx.AsyncClient(timeout=12.0) as client:
                        res = await client.post(url, json=payload)
                        if res.status_code == 200:
                            data = res.json()
                            parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
                            content = "".join(p.get("text", "") for p in parts if isinstance(p, dict)).strip()
                            if content:
                                try:
                                    parsed = json.loads(content)
                                    if isinstance(parsed, dict) and all(k in parsed for k in ["mood", "sleep", "appetite", "pain", "medication_taken"]):
                                        return parsed
                                except Exception:
                                    pass
                        else:
                            logger.warning(f"Gemini extraction model {model_name} returned code {res.status_code}: {res.text}")
                except Exception as e:
                    logger.error(f"Gemini Extraction error with {model_name}: {e}")

        # 2. Try Groq API JSON extraction
        if is_valid_key(self.groq_key):
            try:
                headers = {
                    "Authorization": f"Bearer {self.groq_key}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": "llama-3.3-70b-versatile",
                    "messages": [
                        {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                        {"role": "user", "content": prompt_user}
                    ],
                    "response_format": {"type": "json_object"},
                    "temperature": 0.1
                }
                async with httpx.AsyncClient(timeout=10.0) as client:
                    res = await client.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload)
                    if res.status_code == 200:
                        content = res.json()["choices"][0]["message"]["content"]
                        try:
                            parsed = json.loads(content)
                            if isinstance(parsed, dict) and all(k in parsed for k in ["mood", "sleep", "appetite", "pain", "medication_taken"]):
                                return parsed
                        except Exception:
                            pass
            except Exception as e:
                logger.error(f"Groq Extraction error: {e}")

        # 3. Try OpenAI API JSON extraction
        if is_valid_key(self.openai_key):
            try:
                headers = {
                    "Authorization": f"Bearer {self.openai_key}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": "gpt-4o-mini",
                    "messages": [
                        {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                        {"role": "user", "content": prompt_user}
                    ],
                    "response_format": {"type": "json_object"},
                    "temperature": 0.1
                }
                async with httpx.AsyncClient(timeout=10.0) as client:
                    res = await client.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
                    if res.status_code == 200:
                        content = res.json()["choices"][0]["message"]["content"]
                        try:
                            parsed = json.loads(content)
                            if isinstance(parsed, dict) and all(k in parsed for k in ["mood", "sleep", "appetite", "pain", "medication_taken"]):
                                return parsed
                        except Exception:
                            pass
            except Exception as e:
                logger.error(f"OpenAI Extraction error: {e}")

        # 4. Rule-based heuristic extraction fallback
        return self._fallback_result(transcript, known_medications)


health_extractor = HealthExtractorService()
