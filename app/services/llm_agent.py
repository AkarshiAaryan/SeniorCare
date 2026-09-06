import logging
import httpx
from typing import List, Dict, Any, Optional
from app.config import settings

logger = logging.getLogger("LLMAgent")

SYSTEM_PROMPT = """You are Elena, a warm, caring, respectful, and attentive voice companion for elderly seniors.
You talk like a real, empathetic friend sitting beside the senior in their living room.

YOUR CORE GOALS:
1. Have a genuine, flowing conversation. Acknowledge and react to what the senior citizen just said with authentic empathy and warmth.
2. Maintain conversational context. NEVER repeat introductory greetings like "Hello, how are you feeling" once the conversation is underway.
3. Incorporate their health history: If the patient had recent symptoms (like pain, poor sleep, appetite changes), gently inquire about them.
4. Check on their prescribed medications naturally for the current time of day.
5. Provide space for open sharing: Invite them to share what's on their mind (e.g., "Is there anything else on your mind today, or anything you'd like to chat about?").

CRITICAL VOICE DELIVERY RULES ("WRITING FOR THE EAR"):
- Your response will be spoken aloud via Rime Text-to-Speech.
- Speak in natural, short conversational sentences (10 to 18 words per sentence, maximum 2 sentences per response).
- NEVER use markdown symbols, asterisks (*), hashtags (#), brackets, or bullet points.
- NEVER ask more than ONE question at a time. Seniors get overwhelmed by multi-part questions.
- Speak warmly and gently, with reassuring phrasing.

Patient Profile & Clinical Context:
- Name: {user_name}
- Age: {user_age}
- Prescribed Medications & Timings: {medications_info}
- Recent Health History & Symptoms: {health_history_info}
- Current Time of Day: {time_of_day}
"""

PROACTIVE_PROMPT_TEMPLATE = """You are Elena, a warm, caring voice companion for elderly seniors.
Generate an initial conversational spoken outreach to initiate contact with {user_name} (age {user_age}).

Reason for outreach: {reason_description}
Relevant details: {details}
Recent Health Context: {health_history_info}

CRITICAL RULES:
- Keep the message warm, conversational, and under 25 words.
- Speak in first-person as Elena.
- Ask ONE clear, gentle question.
- Absolutely NO markdown, asterisks, or formatting.
- Natural for speech synthesis via Rime TTS.
"""


def is_valid_key(key: str) -> bool:
    return bool(key and key.strip() and not key.startswith("your_"))


class LLMAgentService:
    def __init__(self):
        self.gemini_key = settings.GEMINI_API_KEY
        self.gemini_model = settings.GEMINI_MODEL
        self.openai_key = settings.OPENAI_API_KEY
        self.groq_key = settings.GROQ_API_KEY
        self.model = settings.LLM_MODEL

    def build_system_prompt(
        self,
        user_name: str,
        user_age: int,
        medications: List[Dict[str, Any]],
        health_history: Optional[List[Any]] = None,
        time_of_day: str = "day"
    ) -> str:
        med_str_list = []
        for m in medications:
            times_str = ", ".join(s.get("time", "") for s in m.get("schedules", [])) if isinstance(m, dict) else ""
            name = m.get("name") if isinstance(m, dict) else getattr(m, "name", "Medicine")
            dosage = m.get("dosage") if isinstance(m, dict) else getattr(m, "dosage", "")
            med_str_list.append(f"{name} ({dosage}) at {times_str}")

        medications_info = "; ".join(med_str_list) if med_str_list else "None registered"

        # Format past health telemetry notes
        history_items = []
        if health_history:
            for h in health_history[:3]:
                h_parts = []
                pain_val = getattr(h, "pain", None) or (h.get("pain") if isinstance(h, dict) else None)
                sleep_val = getattr(h, "sleep", None) or (h.get("sleep") if isinstance(h, dict) else None)
                mood_val = getattr(h, "mood", None) or (h.get("mood") if isinstance(h, dict) else None)
                appetite_val = getattr(h, "appetite", None) or (h.get("appetite") if isinstance(h, dict) else None)

                if pain_val and pain_val not in ["none", "none reported", "None"]:
                    h_parts.append(f"reported pain: {pain_val}")
                if sleep_val and sleep_val not in ["not reported", "good", "normal"]:
                    h_parts.append(f"sleep: {sleep_val}")
                if mood_val and mood_val not in ["not reported", "normal"]:
                    h_parts.append(f"mood: {mood_val}")
                if appetite_val and appetite_val not in ["not reported", "normal"]:
                    h_parts.append(f"appetite: {appetite_val}")
                
                if h_parts:
                    history_items.append("; ".join(h_parts))

        health_history_info = " | ".join(history_items) if history_items else "No prior severe symptoms reported recently."

        return SYSTEM_PROMPT.format(
            user_name=user_name,
            user_age=user_age,
            medications_info=medications_info,
            health_history_info=health_history_info,
            time_of_day=time_of_day
        )

    async def generate_response(
        self,
        messages: List[Dict[str, str]],
        user_name: str = "Friend",
        user_age: int = 75,
        medications: Optional[List[Any]] = None,
        health_history: Optional[List[Any]] = None,
        time_of_day: str = "Morning"
    ) -> str:
        """
        Generate empathetic conversational response given context, health history, and chat history.
        """
        meds = medications or []
        system_instruction = self.build_system_prompt(user_name, user_age, meds, health_history, time_of_day)

        full_messages = [{"role": "system", "content": system_instruction}] + messages

        # 1. Try Gemini API (Native Google REST Endpoint)
        if is_valid_key(self.gemini_key):
            try:
                contents = []
                for m in messages:
                    role = "model" if m.get("role") == "assistant" else "user"
                    contents.append({
                        "role": role,
                        "parts": [{"text": m.get("content", "")}]
                    })

                payload = {
                    "systemInstruction": {
                        "parts": [{"text": system_instruction}]
                    },
                    "contents": contents,
                    "generationConfig": {
                        "temperature": 0.7,
                        "maxOutputTokens": 150
                    }
                }
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.gemini_model}:generateContent?key={self.gemini_key}"
                async with httpx.AsyncClient(timeout=15.0) as client:
                    res = await client.post(url, json=payload)
                    if res.status_code == 200:
                        data = res.json()
                        parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
                        content = "".join(p.get("text", "") for p in parts if isinstance(p, dict)).strip()
                        if content:
                            return content.replace("*", "").replace("#", "").replace("`", "")
                    else:
                        logger.warning(f"Gemini API returned code {res.status_code}: {res.text}")
            except Exception as e:
                logger.error(f"Gemini LLM generation error: {e}")

        # 2. Try Groq API
        if is_valid_key(self.groq_key):
            try:
                headers = {
                    "Authorization": f"Bearer {self.groq_key}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": "llama-3.3-70b-versatile",
                    "messages": full_messages,
                    "temperature": 0.7,
                    "max_tokens": 150
                }
                async with httpx.AsyncClient(timeout=10.0) as client:
                    res = await client.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload)
                    if res.status_code == 200:
                        content = res.json()["choices"][0]["message"]["content"].strip()
                        return content.replace("*", "").replace("#", "")
            except Exception as e:
                logger.error(f"Groq LLM generation error: {e}")

        # 3. Try OpenAI API
        if is_valid_key(self.openai_key):
            try:
                headers = {
                    "Authorization": f"Bearer {self.openai_key}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": self.model,
                    "messages": full_messages,
                    "temperature": 0.7,
                    "max_tokens": 150
                }
                async with httpx.AsyncClient(timeout=10.0) as client:
                    res = await client.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
                    if res.status_code == 200:
                        content = res.json()["choices"][0]["message"]["content"].strip()
                        return content.replace("*", "").replace("#", "")
            except Exception as e:
                logger.error(f"OpenAI LLM generation error: {e}")

        # 4. Contextual Multi-Turn Fallback Engine (Never repeats intro once conversation is active)
        user_msgs = [m.get("content", "").strip() for m in messages if m.get("role") == "user"]
        last_user_msg = (user_msgs[-1] if user_msgs else "").lower()
        turn_count = len(user_msgs)

        if "pain" in last_user_msg or "hurt" in last_user_msg or "sore" in last_user_msg:
            return f"I am so sorry to hear that, {user_name}. Please take it easy and rest. Have you taken your prescribed medicine yet?"
        elif "well" in last_user_msg or "good" in last_user_msg or "fine" in last_user_msg or "great" in last_user_msg:
            if turn_count <= 1:
                return f"I am so glad to hear you are doing well, {user_name}! Have you had a chance to take your prescribed medicine today?"
            else:
                return f"That is wonderful to hear, {user_name}! Is there anything else on your mind today, or anything you would like to share?"
        elif "yes" in last_user_msg and ("medicine" in last_user_msg or "pill" in last_user_msg or "took" in last_user_msg or "taken" in last_user_msg):
            return f"Wonderful news, {user_name}! I am glad you took your medicine. How did you sleep last night?"
        elif "sleep" in last_user_msg or "tired" in last_user_msg or "insomnia" in last_user_msg:
            return f"I understand, {user_name}. Getting enough rest is so important. Is there anything else you would like to tell me today?"
        elif "no" in last_user_msg and ("nothing" in last_user_msg or "else" in last_user_msg or len(last_user_msg) < 15):
            return f"Alright, {user_name}! Thank you for chatting with me today. Have a lovely day, and remember I am always here for you."
        elif turn_count > 1:
            return f"Thank you for sharing that with me, {user_name}. Is there anything else on your mind today?"
        else:
            return f"Hello {user_name}! It is wonderful to speak with you today. How are you feeling this {time_of_day.lower()}?"

    async def generate_proactive_outreach(
        self,
        user_name: str,
        user_age: int,
        reason_type: str,  # 'medication_due' or '3_hour_checkin'
        details: str = "",
        health_history: Optional[List[Any]] = None,
        time_of_day: str = "Daytime"
    ) -> str:
        """
        Generate proactive speech outreach to initiate natural spoken dialogue with the senior.
        """
        reason_desc = (
            "Medication Intake Reminder"
            if reason_type == "medication_due"
            else "Routine 3-Hour Daytime Wellness Check-in"
        )

        history_summary = "No recent complaints"
        if health_history:
            history_summary = ", ".join([f"{h.pain}" for h in health_history if getattr(h, "pain", None)]) or history_summary

        prompt_content = PROACTIVE_PROMPT_TEMPLATE.format(
            user_name=user_name,
            user_age=user_age,
            reason_description=reason_desc,
            details=details,
            health_history_info=history_summary
        )

        # 1. Try Gemini
        if is_valid_key(self.gemini_key):
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.gemini_model}:generateContent?key={self.gemini_key}"
                payload = {
                    "contents": [{"parts": [{"text": prompt_content}]}],
                    "generationConfig": {
                        "temperature": 0.7,
                        "maxOutputTokens": 80
                    }
                }
                async with httpx.AsyncClient(timeout=10.0) as client:
                    res = await client.post(url, json=payload)
                    if res.status_code == 200:
                        data = res.json()
                        parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
                        content = "".join(p.get("text", "") for p in parts if isinstance(p, dict)).strip()
                        if content:
                            return content.replace("*", "").replace("#", "")
            except Exception as e:
                logger.error(f"Gemini proactive generation error: {e}")

        # 2. Try Groq
        if is_valid_key(self.groq_key):
            try:
                headers = {"Authorization": f"Bearer {self.groq_key}", "Content-Type": "application/json"}
                payload = {
                    "model": "llama-3.3-70b-versatile",
                    "messages": [{"role": "user", "content": prompt_content}],
                    "temperature": 0.7,
                    "max_tokens": 80
                }
                async with httpx.AsyncClient(timeout=8.0) as client:
                    res = await client.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload)
                    if res.status_code == 200:
                        return res.json()["choices"][0]["message"]["content"].strip().replace("*", "")
            except Exception as e:
                logger.error(f"Groq proactive generation error: {e}")

        # 3. Try OpenAI
        if is_valid_key(self.openai_key):
            try:
                headers = {"Authorization": f"Bearer {self.openai_key}", "Content-Type": "application/json"}
                payload = {
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt_content}],
                    "temperature": 0.7,
                    "max_tokens": 80
                }
                async with httpx.AsyncClient(timeout=8.0) as client:
                    res = await client.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
                    if res.status_code == 200:
                        return res.json()["choices"][0]["message"]["content"].strip().replace("*", "")
            except Exception as e:
                logger.error(f"OpenAI proactive generation error: {e}")

        # 4. Empathetic Fallback rule-based proactive prompts
        if reason_type == "medication_due":
            return f"Hello {user_name}! It is time for your prescribed medicine: {details}. Have you taken your dose yet?"
        else:
            return f"Hello {user_name}! Elena here with your regular {time_of_day.lower()} check-in. How are you feeling right now?"


llm_agent = LLMAgentService()
