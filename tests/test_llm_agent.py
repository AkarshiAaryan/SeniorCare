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
    messages = [{"role": "user", "content": "My knee really hurts today."}]
    response = await agent.generate_response(messages=messages, user_name="Arthur", user_age=80)
    
    assert "Arthur" in response
    assert "rest" in response.lower() or "sorry" in response.lower() or "medicine" in response.lower()


@pytest.mark.asyncio
async def test_llm_agent_fallback_medicine_confirmation():
    agent = LLMAgentService()
    messages = [{"role": "user", "content": "Yes, I took my morning medicine."}]
    response = await agent.generate_response(messages=messages, user_name="Arthur", user_age=80)
    
    assert "Arthur" in response
    assert "medicine" in response.lower() or "glad" in response.lower() or "sleep" in response.lower()
