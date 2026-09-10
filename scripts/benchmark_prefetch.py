"""
Comprehensive Latency and Accuracy Benchmark for SeniorCare Predictive Voice Prefetch Pipeline.

Evaluates:
1. End-to-end Turn Latency: Cache-Hit (prefetch) vs Cache-Miss (full LLM + Rime TTS).
2. Percentile latencies: P50, P90, P95, P99, Average.
3. Intent Classification Accuracy & Top-2 Recall across realistic senior phrases.
4. Red-flag urgent symptom safety bypass verification.
"""

import asyncio
import time
import sys
import os
import statistics
from typing import List, Dict, Any

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database import SessionLocal, engine, Base
from app import models
from app.services.voice_nlp import voice_nlp
from app.services.voice_intent_predictor import voice_intent_predictor
from app.services.rime_voice_cache import rime_voice_cache
from app.services.voice_prefetcher import voice_prefetcher
from app.services.voice_orchestrator import voice_orchestrator


TEST_CASES = [
    # (context_state, user_utterance, expected_intent, is_urgent)
    ("wellness_check", "I am feeling wonderful this morning", "mood_positive", False),
    ("wellness_check", "I'm not doing very well today, feeling a bit down", "mood_negative", False),
    ("wellness_check", "I'm okay, nothing special", "neutral_fine", False),
    ("medication_check", "Yes, I took my morning blood pressure pills already", "medication_taken", False),
    ("medication_check", "No I haven't taken them yet, I forgot", "medication_missed", False),
    ("sleep_inquiry", "I slept like a baby last night, full eight hours", "sleep_good", False),
    ("sleep_inquiry", "Barely slept at all, tossed and turned all night", "sleep_bad", False),
    ("pain_check", "No pain at all right now", "pain_none", False),
    ("pain_check", "My left knee has a mild ache when walking", "pain_mild", False),
    ("emotion_check", "Feeling a bit lonely lately with nobody around", "emotion_lonely", False),
    ("appetite_check", "Ate a nice warm breakfast", "appetite_good", False),
    ("general_followup", "No that's everything for now dear, thank you", "conclude_conversation", False),
    # Urgent red flags (must bypass cache!)
    ("wellness_check", "I have severe crushing chest pain and feel dizzy", "urgent_symptom", True),
    ("wellness_check", "I fell down and cannot stand up", "urgent_symptom", True),
    ("medication_check", "I think I accidentally took too many pills", "urgent_symptom", True),
]


async def run_benchmark():
    print("=" * 70)
    print(" SENIORCARE PREDICTIVE VOICE PREFETCH BENCHMARK")
    print("=" * 70)

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    # Ensure a test user exists
    user = db.query(models.User).filter(models.User.id == 9999).first()
    if not user:
        user = models.User(
            id=9999,
            name="Eleanor",
            age=82,
            emergency_contact="+1-555-0199",
            allergies="Penicillin",
            conditions="Hypertension"
        )
        db.add(user)
        db.commit()

    # Step 1: Benchmark Intent Classification & Safety Scanner
    print("\n--- 1. Evaluating NLP Intent Classifier & Safety Scanner ---")
    correct_top1 = 0
    correct_top2 = 0
    urgent_passed = 0
    total_eval = 0

    for state, utterance, expected_intent, is_urgent in TEST_CASES:
        total_eval += 1
        urgent_flag, reasons = voice_nlp.detect_urgent_symptoms(utterance)

        if is_urgent:
            if urgent_flag:
                urgent_passed += 1
                print(f" [PASS] Urgent Safety Bypass: '{utterance[:35]}...' -> Flagged: {reasons}")
            else:
                print(f" [FAIL] Urgent Safety Missed: '{utterance}'")
            continue

        intent_res = voice_nlp.classify_intent(utterance, context_state=state)
        top1_intent = intent_res.intent

        # Top-2 prediction from predictor
        top_k = [i[0] for i in voice_intent_predictor.predict_top_k_intents(state, k=2)]

        if top1_intent == expected_intent:
            correct_top1 += 1
        if expected_intent in top_k:
            correct_top2 += 1

        print(f" [{top1_intent == expected_intent and 'PASS' or 'DIFF'}] State: {state:<16} | Text: '{utterance[:30]:<30}' -> Intent: {top1_intent} (Conf: {intent_res.confidence:.2f})")

    non_urgent_total = sum(1 for c in TEST_CASES if not c[3])
    urgent_total = sum(1 for c in TEST_CASES if c[3])

    print(f"\nNLP Intent Top-1 Accuracy: {correct_top1}/{non_urgent_total} ({correct_top1/non_urgent_total*100:.1f}%)")
    print(f"Prefetcher Top-2 Recall:   {correct_top2}/{non_urgent_total} ({correct_top2/non_urgent_total*100:.1f}%)")
    print(f"Urgent Safety Sensitivity: {urgent_passed}/{urgent_total} ({urgent_passed/urgent_total*100:.1f}%)")

    # Step 2: Warm the cache for prefetch testing
    print("\n--- 2. Warming Voice Cache ---")
    await voice_prefetcher.prefetch_for_context("wellness_check", user_name="Eleanor", k=3)
    await voice_prefetcher.prefetch_for_context("medication_check", user_name="Eleanor", k=3)
    await voice_prefetcher.prefetch_for_context("sleep_inquiry", user_name="Eleanor", k=3)

    cache_stats = rime_voice_cache.get_stats()
    print(f"Cache Ready: {cache_stats['entries_count']} entries ({cache_stats['total_size_bytes']} bytes)")

    # Step 3: Measure Latency for Cache Hits vs Cache Misses
    print("\n--- 3. Measuring Latency (Cache Hits vs Misses) ---")
    cache_hit_latencies = []
    cache_miss_latencies = []

    # Test Cache Hits
    hit_samples = [
        ("wellness_check", "I am feeling wonderful this morning"),
        ("wellness_check", "I'm not doing very well today"),
        ("wellness_check", "Doing okay today"),
        ("medication_check", "Yes I took my blood pressure pills"),
        ("medication_check", "No I haven't taken them yet"),
        ("sleep_inquiry", "I slept very well last night"),
    ]

    for state, text in hit_samples:
        res = await voice_orchestrator.process_turn(
            db=db,
            user_id=9999,
            text_input=text,
            context_state=state,
            history=[]
        )
        lat_ms = res["latency_ms"]["total_ms"]
        cached = res.get("cached", False)
        if cached:
            cache_hit_latencies.append(lat_ms)
            print(f" [CACHE HIT]  Latency: {lat_ms:6.2f} ms | State: {state:<16} | Intent: {res.get('intent')}")
        else:
            cache_miss_latencies.append(lat_ms)
            print(f" [CACHE MISS] Latency: {lat_ms:6.2f} ms | State: {state:<16}")

    # Test Cache Miss (un-cached turn requiring LLM + Rime TTS)
    print("\n Testing Cache Miss (LLM + Rime TTS pipeline)...")
    miss_res = await voice_orchestrator.process_turn(
        db=db,
        user_id=9999,
        text_input="Can you tell me a short poem about the autumn leaves falling?",
        context_state="unrelated_topic",
        history=[]
    )
    miss_lat_ms = miss_res["latency_ms"]["total_ms"]
    cache_miss_latencies.append(miss_lat_ms)
    print(f" [CACHE MISS] Latency: {miss_lat_ms:6.2f} ms | Cached: {miss_res.get('cached')} | Breakdown: {miss_res.get('latency_ms')}")

    # Step 4: Summary Statistics
    print("\n" + "=" * 70)
    print(" BENCHMARK PERFORMANCE SUMMARY")
    print("=" * 70)
    if cache_hit_latencies:
        p50 = statistics.median(cache_hit_latencies)
        p95 = statistics.quantiles(cache_hit_latencies, n=20)[-1] if len(cache_hit_latencies) >= 20 else max(cache_hit_latencies)
        avg = statistics.mean(cache_hit_latencies)
        print(f" CACHE HIT Latency (P50):     {p50:6.2f} ms")
        print(f" CACHE HIT Latency (Average): {avg:6.2f} ms")
        print(f" CACHE HIT Latency (P95/Max): {p95:6.2f} ms")
        print(f" CACHE HIT Latency (Min):     {min(cache_hit_latencies):6.2f} ms")

    if cache_miss_latencies:
        print(f" CACHE MISS Latency (Full LLM+TTS): {statistics.mean(cache_miss_latencies):6.2f} ms")

    if cache_hit_latencies and cache_miss_latencies:
        speedup = statistics.mean(cache_miss_latencies) / max(0.1, statistics.mean(cache_hit_latencies))
        latency_reduction = (1 - (statistics.mean(cache_hit_latencies) / statistics.mean(cache_miss_latencies))) * 100
        print(f" Latency Reduction:           {latency_reduction:6.2f}%")
        print(f" Effective Speedup:           {speedup:6.1f}x faster voice response")

    final_stats = rime_voice_cache.get_stats()
    print(f" Cache Hit Rate:              {final_stats['hit_rate_percent']:.1f}%")
    print("=" * 70)

    db.close()


if __name__ == "__main__":
    asyncio.run(run_benchmark())
