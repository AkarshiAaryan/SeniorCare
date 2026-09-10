# 👵 SeniorCare: Project Features, Architecture & Product Pitch

> **An Intelligent, Voice-Native Eldercare Companion & Autonomous Care Coordination Platform**  
> *Powered by Rime TTS, Fast Generative AI, and Clinician-Grade Telemetry Extraction*

---

## 🌟 Executive Pitch: The Problem & The Solution

### The Eldercare Crisis
Over **54 million senior citizens** live independently or in assisted living environments. However, three critical challenges persist:
1. **Medication Non-Adherence**: Seniors frequently miss or double-dose prescribed medications due to cognitive fatigue, confusion, or forgetfulness, leading to preventable hospitalizations.
2. **Social Isolation & Emotional Decline**: Loneliness and undetected depressive episodes severely impact quality of life and accelerate cognitive decline.
3. **Caregiver Blind Spots**: Family members and caregivers cannot be physically present 24/7. Symptom escalation (e.g., escalating pain, poor sleep, loss of appetite) often goes unnoticed until an acute emergency occurs.

### The SeniorCare Solution
**SeniorCare** bridges this divide by introducing **Elena**—an empathetic, proactive voice companion sitting right in the senior's living room. Powered by **Rime AI's ultra-realistic conversational TTS**, Elena talks to the senior in a warm, patient, and human manner. She proactively initiates contact for medication reminders and wellness check-ins, actively listens to the senior's spoken responses, and autonomously extracts structured clinical data (mood, pain levels, sleep quality, and medication adherence) to populate real-time caregiver dashboards and alert systems.

---

## 🚀 Complete Feature Breakdown

### 1. 🎙️ Voice-Native Conversational Companion ("Elena")
* **Hyper-Realistic Spoken Delivery (Rime TTS)**:
  * Powered by Rime's flagship `coda` (conversational) and `mistv3` (low-latency) cloud models.
  * Uses the warm, reassuring `celeste` persona tailored specifically for senior comfort.
  * Configured with a `timeScaleFactor: 1.05` (~5% slower delivery speed) for optimal elderly auditory comprehension.
* **"Writing for the Ear" Text Normalization Engine**:
  * Automatically strips visual markdown symbols (`*`, `#`, `` ` ``, bullet points).
  * Phonetically expands medical dosages, units, and times (e.g., `500mg` $\rightarrow$ `500 milligrams`, `2 tabs` $\rightarrow$ `2 tablets`, `08:00 AM` $\rightarrow$ `8 o'clock AM`).
  * Enforces natural breathing pauses and short sentence lengths (10–18 words per sentence).
* **Caregiver-Grade Clinical Empathy & Medical Triage**:
  * Understands illness and discomfort (e.g., *"I am not feeling very well, do you think I need to consult a doctor?"*).
  * Validates the senior's symptoms with warmth, gently advises consulting a healthcare provider, and inquires about specific pain/fever points.
  * Employs strict negation-aware sentiment parsing so phrases like *"not feeling good"* or *"hardly slept"* are never misclassified as positive.
* **Dual-Layer Audio Pipeline**:
  * Primary: High-fidelity streaming audio synthesized via Rime AI TTS API.
  * Fallback: Browser Web SpeechSynthesis if offline or running in low-bandwidth conditions.
* **Real-Time Live Speech-to-Text**:
  * Employs the browser Web Speech API for instantaneous on-screen visual feedback as the senior speaks.
  * Captures high-clarity audio blobs using Opus/WebM MediaRecorder for cloud transcription.

---

### 2. ⚡ Hard Voice Engineering: Interruption Safety & Turn State Store
Real-world voice conversations with elderly seniors are non-linear—seniors frequently interrupt, change their minds mid-sentence, or speak again before an assistant finishes talking.

* **Turn State Machine (`TurnStateStore`)**:
  * Every voice turn is tagged with a unique `turn_id` tracked per user in `app/services/voice_orchestrator.py`.
* **Stale-Response Protection**:
  * If a senior starts speaking a new sentence while an earlier turn is still generating or speaking, older in-flight turns are immediately marked stale and rejected.
* **Instant Client Playback Halting**:
  * Frontend audio playback stops immediately when new user voice activity is detected, eliminating overlapping speech and audio desynchronization.
* **Benchmark Proven**:
  * Verified via `scripts/run_interrupt_benchmark.py` with a 100% (50/50 trials) success rate in stale-turn invalidation.

---

### 3. ⏰ Autonomous Proactive Wellness Scheduler
Rather than waiting for an elderly patient to remember to open an app, SeniorCare proactively initiates contact:

* **3-Hour Daytime Wellness Check-Ins**:
  * Background `APScheduler` triggers scheduled check-ins at regular daytime intervals (e.g., 09:00, 12:00, 15:00, 18:00, 21:00).
* **Prescription-Synchronized Reminders**:
  * Automatically inspects the patient's database schedule and triggers timely voice reminders when doses are due.
* **Natural Conversational Outreach Generation**:
  * Elena generates contextual outreach prompts (e.g., *"Hello John! Elena here for your afternoon check-in. How are you feeling right now?"*) and synthesizes audio ahead of modal presentation.

---

### 4. 🩺 Autonomous Clinical Health Extraction & Adherence Telemetry
Every conversational exchange is processed by an intelligent clinical extraction engine (`app/services/health_extractor.py`):

* **Structured Telemetry Captured**:
  * **Mood**: `good`, `normal`, `low`, `anxious`, `lonely`, `tired`
  * **Sleep Quality**: `good`, `poor`, `interrupted`, `insomnia`
  * **Appetite**: `good`, `poor`, `low`, `normal`
  * **Pain Index**: Specific locations & severity (e.g., `mild knee pain`, `lower back ache`, `headache`)
  * **Medication Adherence**: `true` / `false` / `null` mapped to scheduled prescription times
  * **Urgent Red Flags**: `true` / `false` for acute distress or severe symptoms
  * **Clinician Summary**: 1-sentence plain-English summary for caregiver review
* **Automatic Database Persistence**:
  * Generates database records in `HealthRecord`, `MedicationLog`, `Conversation`, and `EventLog`.

---

### 5. 👥 Caregiver Roster & Multi-Day Analytics Portal
* **Caregiver Authentication**: Secure token-based session management and caregiver sign-in.
* **Assigned Patient Roster**:
  * Overview cards displaying patient age, contact, assigned caregiver, active prescription count, and live health status badge (`Active`, `High Risk`, `Missed Medication`).
* **Patient Deep-Dive Detail Dashboard**:
  * **Prescription Manager**: Add, edit, and schedule medications with custom dosages and times.
  * **Multi-Day Telemetry Graphs**: Visual trend lines for mood fluctuations, sleep quality, and pain severity.
  * **Medication Adherence Tracker**: Timestamps of confirmed intakes vs. scheduled intervals.
  * **Transcript History**: Chronological log of all senior-assistant conversations with extracted JSON metrics.
  * **One-Click Instant Outreach Trigger**: Allows caregivers to trigger an immediate check-in turn on demand.
* **Emergency Panic & Alert Escalation**:
  * Real-time notifications for missed medications, reported severe pain, or panic button activations.

---

### 6. 🛡️ Multi-Model Resilient LLM Cascade
To guarantee 100% uptime and resilience against rate limits or cloud service hiccups:
1. **Google Gemini Cascade**: Tries active models (`gemini-2.5-flash-lite` $\rightarrow$ `gemini-flash-latest` $\rightarrow$ `gemini-2.5-flash`) with zero-latency token streaming (`thinkingBudget: 0`).
2. **Groq Failover**: Ultra-fast LLaMA-3.3-70B-Versatile endpoint.
3. **OpenAI Failover**: GPT-4o / GPT-4o-mini endpoint.
4. **Caregiver Heuristic Engine**: Negation-aware, empathetic rule-based companion fallback if internet connectivity is completely severed.

---

## 📊 Summary of Implemented Features & Endpoints

| Component | Feature / Capability | Implementation File |
| :--- | :--- | :--- |
| **Voice Synthesis** | Rime TTS Coda/Mist integration with Celeste voice & 1.05x speed | `app/services/rime_tts.py` |
| **Text Normalization** | "Writing for the Ear" medical expansion & markdown stripping | `app/services/rime_tts.py` |
| **Interruption Safety** | Turn state store & stale response rejection | `app/services/voice_orchestrator.py` |
| **Conversational AI** | Caregiver clinical prompt, medical triage & multi-turn history | `app/services/llm_agent.py` |
| **Multi-Model Cascade** | Gemini 2.5 Flash Lite + Groq + OpenAI zero-downtime failover | `app/services/llm_agent.py` |
| **Health Telemetry** | Autonomous structured extraction of mood, pain, sleep, meds | `app/services/health_extractor.py` |
| **Proactive Check-Ins** | 3-hour daytime intervals & prescription-time voice outreach | `app/services/scheduler.py` |
| **Caregiver Portal** | Patient roster, multi-day analytics, prescription scheduler | `frontend/src/pages/CaregiverDashboard.jsx` |
| **Voice Modal UI** | Live STT visualization, pulsing mic, instant cancel on speak | `frontend/src/components/VoiceModal.jsx` |
| **Test Suite** | 48 automated tests covering router, TTS, STT, LLM & Benchmarks | `tests/` & `test_voice_ai.py` |

---

## 🏆 Why SeniorCare Wins

1. **True Voice-Native Design**: Tailored specifically for seniors—slower speech pacing, warm conversational voice, phonetic dosage clarity, and instant interruption tolerance.
2. **Autonomous Proactivity**: Eliminates user burden by initiating contact at clinical intervals and medication times.
3. **Closing the Caregiver Loop**: Transforms casual living room voice chats into actionable clinician telemetry, alerting caregivers before emergencies happen.
4. **Production-Ready & Fully Tested**: 100% test pass rate across 48 unit/integration tests with robust multi-model resilience.
