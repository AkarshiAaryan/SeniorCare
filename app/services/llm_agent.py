import logging
import httpx
from typing import List, Dict, Any, Optional
from app.config import settings

logger = logging.getLogger("LLMAgent")

SYSTEM_PROMPT = """You are Elena, a warm, caring, and attentive voice companion for elderly seniors.
Your goal is to have a short, friendly daily check-in with the senior citizen to ask how they are feeling, check their sleep and appetite, ask about any pain, and verify whether they have taken their prescribed medications.

CRITICAL VOICE DELIVERY RULES ("WRITING FOR THE EAR"):
1. Your response will be spoken aloud using Rime Text-to-Speech.
2. Speak warmly, respectfully, and gently as if sitting beside them in their living room.
3. Keep your sentences short, simple, and natural (10 to 15 words per sentence maximum).
4. NEVER use markdown symbols, asterisks (*), hashtags (#), brackets, or bullet points.
5. NEVER ask more than one question at a time. Seniors get overwhelmed by multi-part questions.
6. Use natural conversational phrasing, friendly greetings, and gentle reassurance.
7. If the user mentions pain, poor sleep, or missing a medication, respond with warmth and care.

Context about the patient:
- Name: {user_name}
- Age: {user_age}
- Prescribed Medications & Timings: {medications_info}
- Current Time of Day: {time_of_day}
"""


class LLMAgentService:
    def __init__(self):
        self.openai_key = settings.OPENAI_API_KEY
        self.groq_key = settings.GROQ_API_KEY
        self.model = settings.LLM_MODEL

    def build_system_prompt(self, user_name: str, user_age: int, medications: List[Dict[str, Any]], time_of_day: str = "day") -> str:
        med_str_list = []
        for m in medications:
            times_str = ", ".join(s.get("time", "") for s in m.get("schedules", [])) if isinstance(m, dict) else ""
            name = m.get("name") if isinstance(m, dict) else getattr(m, "name", "Medicine")
            dosage = m.get("dosage") if isinstance(m, dict) else getattr(m, "dosage", "")
            med_str_list.append(f"{name} ({dosage}) at {times_str}")

        medications_info = "; ".join(med_str_list) if med_str_list else "None registered"

        return SYSTEM_PROMPT.format(
            user_name=user_name,
            user_age=user_age,
            medications_info=medications_info,
            time_of_day=time_of_day
        )

    async def generate_response(
        self,
        messages: List[Dict[str, str]],
        user_name: str = "Friend",
        user_age: int = 75,
        medications: Optional[List[Any]] = None,
        time_of_day: str = "Morning"
    ) -> str:
        """
        Generate empathetic conversational response given context and chat history.
        """
        meds = medications or []
        system_instruction = self.build_system_prompt(user_name, user_age, meds, time_of_day)

        full_messages = [{"role": "system", "content": system_instruction}] + messages

        # 1. Try Groq API
        if self.groq_key:
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
                        return content
            except Exception as e:
                logger.error(f"Groq LLM generation error: {e}")

        # 2. Try OpenAI API
        if self.openai_key:
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
                        return content
            except Exception as e:
                logger.error(f"OpenAI LLM generation error: {e}")

        # 3. Fallback empathetic response engine for offline / testing mode
        last_user_msg = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                last_user_msg = m.get("content", "").lower()
                break

        if "pain" in last_user_msg or "hurt" in last_user_msg:
            return f"I am so sorry to hear that, {user_name}. Please take it easy and rest. Have you taken your morning medicine yet?"
        elif "yes" in last_user_msg and ("medicine" in last_user_msg or "pill" in last_user_msg or "took" in last_user_msg):
            return f"Wonderful news, {user_name}! I am glad you took your medicine. How did you sleep last night?"
        elif "sleep" in last_user_msg or "tired" in last_user_msg:
            return f"I understand, {user_name}. Getting enough rest is so important. Make sure to drink some water and stay comfortable today."
        else:
            return f"Hello {user_name}! It is wonderful to speak with you today. How are you feeling this morning?"


llm_agent = LLMAgentService()
