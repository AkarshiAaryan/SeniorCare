# SeniorCare — Hands-Free Interruption Recovery System

SeniorCare is a voice-native eldercare assistant focused on one concrete hard problem: interruption-safe conversation under real-time turn overlap. It supports hands-free speech detection, turn-scoped WebSocket audio, cancellation of obsolete work, and streamed assistant audio.

The project centers on a turn-state machine, stale-response protection, and explicit cancellation of active audio when a newer user request arrives. The goal is a reliable voice system that behaves correctly when a senior interrupts Elena during playback or while the model is still working.

---

## Why this is the hard voice problem

In a voice assistant, the most important correctness issue is not the happy path. It is the moment when:

- the user speaks while the assistant is still talking,
- a new request supersedes an older one,
- a delayed LLM or TTS response arrives late,
- or a stale audio result should be discarded rather than played.

This project is designed around that failure mode.

---

## What is implemented

### Hands-free speech detection
- The browser can keep a microphone stream open in Hands-Free mode.
- An AudioWorklet RMS voice-activity detector starts a turn after confirmed speech and closes it after approximately 700 ms of silence.
- Browser echo cancellation, noise suppression, and automatic gain control are requested for microphone capture.

### Turn-state machine and cancellation
- Each user turn carries a stable `turn_id` through backend and frontend flows.
- The active turn is tracked per user in the orchestrator.
- A new speech start cancels the previous active turn and its background processing task.
- Older turns are marked stale and rejected if superseded.

### Stale-response protection
- The backend rechecks the `turn_id` after STT, LLM work, TTS, and immediately before persistence.
- The frontend ignores turn-tagged audio/results that do not match the active turn.
- This prevents older assistant output from overwriting the latest user intent.

### Real interruption handling
- When a user starts speaking again, active browser speech and audio playback are canceled.
- The WebSocket remains receptive while STT, LLM, and TTS work run in a cancellable background task.
- Rime TTS is sent as `tts_start`, `tts_chunk`, and `tts_end` events; the browser plays only chunks belonging to the active turn.
- This prevents the classic “old voice continues after I interrupt” bug.

### Tool cancellation / reconciliation
- Microphone turns use WebSocket as their authoritative processing path, preventing duplicate HTTP and WebSocket requests for one utterance.
- Out-of-order responses are explicitly reconciled against the newest active turn.

---

## Repository focus

The important implementation points are in:

- [app/services/voice_orchestrator.py](app/services/voice_orchestrator.py)
- [app/routers/voice.py](app/routers/voice.py)
- [frontend/src/components/VoiceModal.jsx](frontend/src/components/VoiceModal.jsx)
- [frontend/src/worklets/vad-processor.js](frontend/src/worklets/vad-processor.js)
- [scripts/run_interrupt_benchmark.py](scripts/run_interrupt_benchmark.py)

---

## Benchmark and acceptance criteria

The hard-voice benchmark measures:

1. stale-turn rejection rate,
2. turn-switch latency,
3. whether the newest turn remains active after interruption,
4. whether the app cancels old speech before the new response is finalized.

The automated benchmark verifies turn replacement. The WebSocket flow is additionally designed so that new speech can be received while a previous turn is still awaiting STT, LLM, or TTS work.

Current measured result from the project benchmark:

- Trials: 50
- Stale-turn rejection: 50/50
- Median switch latency: 0.01 ms
- Result: PASS

This is the evidence claim for the interruption-safe voice flow.

---

## Run locally

### Backend
```bash
source .venv/bin/activate
PYTHONPATH=. uvicorn app.main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

### Benchmark
```bash
source .venv/bin/activate
PYTHONPATH=. python scripts/run_interrupt_benchmark.py
```

### Targeted regression
```bash
source .venv/bin/activate
PYTHONPATH=. pytest -q tests/test_voice_router.py
```

---

## Notes

This project deliberately avoids broad feature work in favor of the hardest practical requirement in voice AI: making a real conversation resilient to interruption and stale asynchronous results.

---

## 📡 API Reference Overview

| HTTP Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/voice/tts` | Synthesize custom text to MP3 audio stream using Rime TTS |
| `POST` | `/voice/stt` | Transcribe uploaded audio file to text |
| `POST` | `/voice/process-turn` | Process a text turn (LLM + Rime TTS + Health Extraction + DB Save) |
| `POST` | `/voice/process-audio-turn` | Process a microphone audio recording turn |
| `POST` | `/voice/cancel/{user_id}` | Cancel the currently active voice turn |
| `WebSocket` | `/voice/ws/{user_id}` | Turn-tagged microphone input plus streamed TTS output (`speech_start`, `audio_chunk`, `speech_end`, `tts_chunk`) |
| `POST` | `/caregiver/panic` | Trigger immediate emergency alert from the elderly interface |
| `GET` | `/caregiver/analytics/{user_id}` | Fetch 7-day adherence, sleep trends, mood distribution & pain logs for Recharts |
| `POST` | `/caregiver/alerts/{alert_id}/resolve` | Mark an emergency or scheduler alert as resolved |
| `GET` | `/daily-report/{user_id}` | Generate consolidated daily caregiver report with clinical notes |
| `POST` | `/medications` | Register prescription with multiple daily intake timings |
| `POST` | `/medication-logs` | Record dose intake status (`taken: true/false`) |
| `GET` | `/events/pending` | Query unprocessed scheduler check-in and medication due reminders |

---

## 📜 License
This project is licensed under the **MIT License**.
