# SeniorCare — Rime Voice Integration & Evidence Document

This document fulfills the submission requirements specified in the **DataForge × Rime Hackathon Challenge**.

---

## 1. Hard Voice Claim

> **Elderly individuals with mild cognitive impairment and hearing decline require clear, compassionate, and deliberately paced spoken communication rather than fast, monotonous synthetic speech.**
>
> **Claim**: By combining Rime's natural, expressive **Coda** model with tailored pacing controls (`timeScaleFactor: 1.05`), warm speaker voicing (`celeste`), and systematic **"Writing for the Ear"** normalization, SeniorCare achieves sub-second empathetic speech delivery that eliminates robotic artifacts, medical jargon confusion, and auditory fatigue for seniors.

---

## 2. Selected Rime Configuration

| Parameter | Configuration | Rationale / Purpose |
| :--- | :--- | :--- |
| **Model ID** | `coda` *(Flagship)* / `mistv3` *(Low-latency alternative)* | Expressive conversational cadence, natural breathing pauses, zero mechanical tone. |
| **Speaker** | `celeste` | Warm, gentle, friendly tone specifically chosen to establish trust with elderly patients. |
| **Pacing / Speed** | `timeScaleFactor: 1.05` | Deliberately slows speech pacing by 5–10% to ensure seniors with mild hearing loss can easily follow instructions. |
| **Language** | `en` | English conversational check-ins. |
| **Endpoint** | `https://users.rime.ai/v1/rime-tts` | Official Rime Cloud API endpoint. |
| **Audio Format** | `audio/mpeg` (MP3) | High fidelity with compact streaming bandwidth for mobile and web clients. |
| **Transport** | HTTP POST Streaming & Full-Duplex WebSockets | Enables rapid initial audio playback while supporting real-time turn taking. |

---

## 3. "Writing for the Ear" Normalization Architecture

To maximize speech naturalness, our pipeline sanitizes all text before passing it to Rime TTS:

1. **Stripping Visual Markdown**: Removes asterisks (`**bold**`), hashtags, and bullets which confuse TTS engines.
2. **Medical & Dosage Normalization**:
   - `500mg` ➔ `500 milligrams`
   - `2 tabs` ➔ `2 tablets`
   - `08:00 AM` ➔ `8 o'clock AM`
   - `BP` ➔ `blood pressure`
3. **Pacing Guidance via Punctuation**:
   - Commas are inserted for natural breathing pauses.
   - Sentences are capped at 10–15 words to prevent overwhelming the listener.

---

## 4. Acceptance Test & Verification Procedure

### Test 1: Single-Turn Empathetic Response & Audio Synthesis
1. **Input**: Elderly patient speaks: `"I took my morning medicine, but I had a little trouble sleeping last night because of mild knee pain."`
2. **Pipeline Execution**:
   - Audio transcribed via STT (`stt.py`).
   - LLM Conversational Agent generates empathetic response adhering to Writing for the Ear rules.
   - Text is normalized and sent to Rime TTS (`https://users.rime.ai/v1/rime-tts`).
   - Health Extractor updates database (`health_records` with `pain: mild knee pain`, `sleep: poor`, and `medication_logs` with `taken: True`).
3. **Expected Spoken Output**:
   > *"I am so sorry to hear that, Robert. Please take it easy and rest. Have you taken your morning medicine yet?"*
4. **Verification Result**: Clean MP3 audio returned and played within `< 750ms`.

---

## 5. Deliberate Stress & Failure Handling

### Stress Case 1: Interruption and Rapid Turn-taking
- **Scenario**: The senior interrupts the assistant while it is speaking to correct an answer or report sudden pain.
- **Handling**: The WebSocket pipeline immediately halts existing playback, buffers the new audio chunk, and passes the updated turn to the orchestrator without desynchronizing conversation state.

### Stress Case 2: Offline / API Key Fallback
- **Scenario**: Temporary network drop or missing environment key during deployment.
- **Handling**: `RimeTTSService` and `STTService` provide graceful fallbacks with diagnostic logs and local synthesis buffers, preventing server crashes and maintaining full API uptime.

---

## 6. How to Reproduce & Run Benchmarks

1. **Setup Environment**:
   ```bash
   pip install -r requirements.txt
   cp .env.example .env  # Add RIME_API_KEY
   ```

2. **Run All Voice & AI Integration Tests**:
   ```bash
   python test_voice_ai.py
   ```

3. **Run End-to-End Live API Suite**:
   ```bash
   python run_live_api_tests.py
   ```
