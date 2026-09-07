# SeniorCare — Interruption Recovery Evidence

This document records the actual hard-voice claim implemented in SeniorCare: interruption-safe conversation with stale-response protection and fast turn recovery.

---

## 1. Hard voice claim

> SeniorCare is not primarily a generic eldercare dashboard. Its hard technical claim is that it can safely handle interrupted voice turns and reject stale asynchronous results without allowing an older assistant response to override the newest user intent.

This is the failure mode that matters in real voice systems: a user interrupts mid-speech, a delayed model response arrives late, and the assistant must recover without confusing the conversation state.

---

## 2. The implemented system

### Turn-state model
The orchestration layer tracks the active turn per user and rejects any response whose `turn_id` is no longer current.

Relevant implementation:
- [app/services/voice_orchestrator.py](app/services/voice_orchestrator.py)

### Frontend interruption handling
The voice modal explicitly cancels active speech synthesis and any in-flight audio when a new turn begins or the user interrupts.

Relevant implementation:
- [frontend/src/components/VoiceModal.jsx](frontend/src/components/VoiceModal.jsx)
- [frontend/src/services/api.js](frontend/src/services/api.js)

### API contract and response reconciliation
Each voice request carries a turn id, and stale results are returned with `stale: true` so the frontend discards them rather than speaking or rendering old content.

---

## 3. Benchmark definition

The benchmark simulates the interruption pattern directly:

1. A first turn becomes active.
2. A second turn is registered as newer.
3. The older response is checked against the current active turn.
4. The stale result must be rejected and the newest turn must remain active.

Benchmark script:
- [scripts/run_interrupt_benchmark.py](scripts/run_interrupt_benchmark.py)

---

## 4. Measured results

Fresh benchmark run:

- Trials: 50
- Stale-turn rejection: 50/50
- Recovery success: 50/50
- Median switch latency: 0.01 ms
- P95 latency: 0.01 ms
- Status: PASS

This verifies that stale responses are consistently discarded and the newest turn remains authoritative.

---

## 5. Regression verification

Verified command:

```bash
source .venv/bin/activate && PYTHONPATH=. pytest -q tests/test_voice_router.py
```

Result:

- 7 passed
- 0 failed

This confirms the turn-state logic and stale-response handling remain stable under the relevant API tests.

---

## 6. Scope note

This project deliberately narrows scope to the hardest voice-system behavior instead of adding broad product features. The claim is not “we support every eldercare workflow.” The claim is that the system can recover correctly under interruption and stale async outputs, which is the core engineering challenge in a real-time voice assistant.
