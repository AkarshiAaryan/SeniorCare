import pytest
from app.services.llm_agent import LLMAgentService


def test_llm_prompt_structure():
    agent = LLMAgentService()
    meds = [{"name": "Lisinopril", "dosage": "10mg", "schedules": [{"time": "08:00"}]}]
    prompt = agent.build_system_prompt(user_name="Eleanor", user_age=84, medications=meds, time_of_day="Morning")
    
    assert "Eleanor" in prompt
    assert "84" in prompt
    assert "Lisinopril" in prompt
    assert "WRITING FOR THE EAR" in prompt


@pytest.mark.asyncio
async def test_llm_agent_fallback_pain():
    agent = LLMAgentService()
    agent.gemini_key = ""
    agent.groq_key = ""
    agent.openai_key = ""
    messages = [{"role": "user", "content": "My knee really hurts today."}]
    response = await agent.generate_response(messages=messages, user_name="Arthur", user_age=80)
    
    assert "Arthur" in response
    assert "rest" in response.lower() or "sorry" in response.lower() or "medicine" in response.lower()


@pytest.mark.asyncio
async def test_llm_agent_fallback_medicine_confirmation():
    agent = LLMAgentService()
    agent.gemini_key = ""
    agent.groq_key = ""
    agent.openai_key = ""
    messages = [{"role": "user", "content": "Yes, I took my morning medicine."}]
    response = await agent.generate_response(messages=messages, user_name="Arthur", user_age=80)
    
    assert "Arthur" in response
    assert "medicine" in response.lower() or "glad" in response.lower() or "sleep" in response.lower()


@pytest.mark.asyncio
async def test_llm_agent_fallback_not_feeling_well_doctor():
    agent = LLMAgentService()
    agent.gemini_key = ""
    agent.groq_key = ""
    agent.openai_key = ""
    messages = [{"role": "user", "content": "I am not feeling very well do you think I need to consult to doctor"}]
    response = await agent.generate_response(messages=messages, user_name="John Doe", user_age=78)
    
    # Must NOT say "wonderful" or positive celebration
    assert "wonderful" not in response.lower()
    assert "glad" not in response.lower()
    assert "doctor" in response.lower() or "sorry" in response.lower() or "symptoms" in response.lower()


@pytest.mark.asyncio
async def test_llm_agent_fallback_emotional_distress():
    agent = LLMAgentService()
    agent.gemini_key = ""
    agent.groq_key = ""
    agent.openai_key = ""
    messages = [{"role": "user", "content": "I am feeling down and lonely today"}]
    response = await agent.generate_response(messages=messages, user_name="John Doe", user_age=78)
    
    assert "wonderful" not in response.lower()
    assert "down" in response.lower() or "sorry" in response.lower() or "mind" in response.lower()
