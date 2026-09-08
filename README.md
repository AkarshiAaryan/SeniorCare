# 👵 SeniorCare — Voice-Native Eldercare & Interruption-Safe Companion

[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18+-61DAFB.svg?logo=react&logoColor=black)](https://react.dev)
[![Rime TTS](https://img.shields.io/badge/Rime%20TTS-Coda%20%7C%20Mist-6366F1.svg)](https://rime.ai)
[![Tailwind CSS](https://img.shields.io/badge/TailwindCSS-3.4+-38B2AC.svg?logo=tailwindcss&logoColor=white)](https://tailwindcss.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**SeniorCare** is an intelligent, voice-native elderly care assistance platform built for the **DataForge × Rime Hackathon Challenge**. It empowers elderly citizens to manage their daily medications, report their health and emotional well-being through warm conversational voice interactions powered by **Rime TTS**, and provides caregivers with real-time dashboards, multi-day health analytics, and instant emergency panic alerting.

---

## 🎙️ Rime TTS Integration & Voice Architecture

SeniorCare relies on **Rime's Cloud TTS API** as its primary voice delivery engine, specifically engineered for elderly listeners.

### Exact Rime Production Configuration
* **Endpoint**: `https://users.rime.ai/v1/rime-tts`
* **Model ID**: `coda` *(Flagship conversational model)* or `mistv3` *(Ultra-low latency alternative)*
* **Speaker**: `celeste` *(Warm, gentle, reassuring voice tone for elderly users)*
* **Pacing & Speed**: `timeScaleFactor: 1.05` *(Slowing delivery speed by ~5% for elderly hearing clarity)*
* **Language**: `en`
* **Audio Format**: `audio/mpeg` (MP3)
* **Transport**: HTTP POST Streaming & WebSockets

### "Writing for the Ear" Text Normalization
To guarantee optimal speech synthesis quality, all text passed to Rime TTS is normalized in [app/services/rime_tts.py](file:///home/regenesis/Desktop/Web%20Dev/SeniorCareMain/SeniorCare/app/services/rime_tts.py):
- Strips visual markdown formatting (`*`, `#`, `` ` ``, bullet points).
- Expands medical abbreviations and dosages (`500mg` ➔ `500 milligrams`, `2 tabs` ➔ `2 tablets`, `08:00 AM` ➔ `8 o'clock AM`).
- Enforces natural breathing pauses using punctuation and short sentence structures (max 15-20 words per response).

---

## ⚡ Hard Voice Engineering: Interruption Safety & Turn State Store

SeniorCare tackles the hard voice problem of **full-duplex interruption recovery and stale-response rejection**:

1. **Turn-State Machine**: Each user turn carries a unique `turn_id` tracked per user in `TurnStateStore` ([app/services/voice_orchestrator.py](file:///home/regenesis/Desktop/Web%20Dev/SeniorCareMain/SeniorCare/app/services/voice_orchestrator.py)).
2. **Stale-Response Protection**: If a senior interrupts or speaks a new prompt while the assistant is speaking, older in-flight turns are marked stale and rejected.
3. **Immediate Audio Cancellation**: The frontend ([VoiceModal.jsx](file:///home/regenesis/Desktop/Web%20Dev/SeniorCareMain/SeniorCare/frontend/src/components/VoiceModal.jsx)) immediately halts current browser playback upon new voice detection, preventing desynchronization.

---

## 🚀 Complete Setup & Installation Guide

### Prerequisites
* **Python**: `3.10` or higher
* **Node.js**: `18.0` or higher & `npm`

### 1. Repository Setup & Environment Configuration

Clone the repository and prepare your environment variables:

```bash
git clone https://github.com/AkarshiAaryan/SeniorCare.git
cd SeniorCare

# Create and populate .env file
cp .env.example .env
```

Open `.env` and fill in your API credentials:

```env
# Rime AI TTS Configuration
RIME_API_KEY=your_actual_rime_api_key_here
RIME_API_URL=https://users.rime.ai/v1/rime-tts
RIME_MODEL_ID=coda
RIME_SPEAKER=celeste
RIME_TIME_SCALE_FACTOR=1.05
RIME_AUDIO_FORMAT=audio/mpeg

# LLM & Intelligence Configuration
GEMINI_API_KEY=your_actual_gemini_api_key_here
GEMINI_MODEL=gemini-3.6-flash
GROQ_API_KEY=your_groq_api_key_here
LLM_MODEL=gemini-3.6-flash

# Speech-to-Text Configuration
STT_PROVIDER=gemini
```

### 2. Backend Setup & Server Execution

```bash
# Create virtual environment (optional)
python3 -m venv .venv
source .venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt

# Launch FastAPI backend server
uvicorn app.main:app --reload --port 8000
```
* The backend API will start at: `http://127.0.0.1:8000`
* Interactive API Documentation (Swagger UI): `http://127.0.0.1:8000/docs`

### 3. Frontend Setup & Execution

In a new terminal window:

```bash
cd frontend

# Install Node dependencies
npm install

# Launch Vite development server
npm run dev
```
* The web app will open at: `http://localhost:5173`

---

## 🧪 Comprehensive Testing & Verification Suite (For Judges)

You can verify all backend logic, Rime TTS integrations, STT pipelines, and interruption benchmarks using the commands below:

### 1. Full Pytest Automated Unit & Router Suite (45/45 Passed)
Runs the complete test suite covering Rime TTS, STT, LLM Agent, Turn State Store, Caregiver Analytics, and Scheduler:
```bash
PYTHONPATH=. pytest
```

### 2. Voice AI & Rime Pipeline Integration Test
Executes text normalization, health extraction, Rime TTS synthesis, and process-turn flows:
```bash
python test_voice_ai.py
```

### 3. Live REST API Verification Suite
Simulates end-to-end patient onboarding, prescription setup, voice turn processing, check-in events, and daily clinical report generation:
```bash
python run_live_api_tests.py
```

### 4. Hard Voice Interruption & Rejection Benchmark
Measures turn-switch latency, stale-turn rejection rate (50/50 trials), and state invalidation:
```bash
python scripts/run_interrupt_benchmark.py
```

### 5. Frontend Production Build Verification
Verifies zero syntax errors or missing dependencies in the React app:
```bash
cd frontend && npm run build
```

---

## 🛡️ Failure Behavior & Fallback Resilience Architecture

If external API limits or network dropouts occur during evaluation, SeniorCare gracefully maintains uptime:
- **Speech-to-Text (STT)**: Automatically failover from Gemini model candidate list (`gemini-3.6-flash`, `gemini-2.5-flash`) to Groq Whisper (`whisper-large-v3`), before falling back to local mock transcription.
- **LLM Agent**: Automatically failover across Gemini models, Groq LLaMA-3.3-70B, and OpenAI GPT, before falling back to an offline rule-based empathetic caregiver engine ([llm_agent.py](file:///home/regenesis/Desktop/Web%20Dev/SeniorCareMain/SeniorCare/app/services/llm_agent.py)).
- **Rime TTS**: Returns warning logs and mock audio streams if the API key is missing or quota is exhausted, ensuring the server never crashes.

---

## 📄 Hackathon Evidence Document

For full details on our hard-voice claims, acceptance tests, pacing benchmarks, and judging criteria, see [RIME_EVIDENCE.md](file:///home/regenesis/Desktop/Web%20Dev/SeniorCareMain/SeniorCare/RIME_EVIDENCE.md).

---

## 📡 API Reference Overview

| HTTP Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/voice/tts` | Synthesize custom text to MP3 audio stream using Rime TTS |
| `POST` | `/voice/stt` | Transcribe uploaded audio file to text |
| `POST` | `/voice/process-turn` | Process a text turn (LLM + Rime TTS + Health Extraction + DB Save) |
| `POST` | `/voice/process-audio-turn` | Process a microphone audio recording turn |
| `WebSocket` | `/voice/ws/{user_id}` | Real-time bidirectional voice stream for live conversations |
| `POST` | `/caregiver/panic` | Trigger immediate emergency alert from the elderly interface |
| `GET` | `/caregiver/analytics/{user_id}` | Fetch 7-day adherence, sleep trends, mood distribution & pain logs |
| `GET` | `/daily-report/{user_id}` | Generate consolidated daily caregiver report with clinical notes |
| `POST` | `/medications` | Register prescription with multiple daily intake timings |

---

## 📜 License
This project is licensed under the **MIT License**.
