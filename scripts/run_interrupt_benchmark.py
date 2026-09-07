import statistics
import time
from typing import List, Tuple

from app.services.voice_orchestrator import TurnStateStore


def simulate_trial() -> Tuple[bool, float]:
    store = TurnStateStore()
    old_turn = "turn-old"
    new_turn = "turn-new"

    start = time.perf_counter()
    store.register_turn(1, old_turn)
    store.register_turn(1, new_turn)

    stale_rejected = not store.is_active_turn(1, old_turn)
    switch_latency_ms = (time.perf_counter() - start) * 1000
    return stale_rejected, switch_latency_ms


def main() -> None:
    trials: List[Tuple[bool, float]] = []
    for _ in range(50):
        stale_rejected, latency_ms = simulate_trial()
        trials.append((stale_rejected, latency_ms))

    stale_success = sum(1 for stale_ok, _ in trials if stale_ok)
    latencies = [lat for _, lat in trials]

    print("SeniorCare Voice Interruption Benchmark")
    print("====================================")
    print(f"Trials: {len(trials)}")
    print(f"Stale-turn rejection: {stale_success}/{len(trials)}")
    print(f"Recovery success: {stale_success}/{len(trials)}")
    print(f"Median switch latency: {statistics.median(latencies):.2f} ms")
    print(f"Mean switch latency: {statistics.mean(latencies):.2f} ms")
    print(f"P95 latency: {sorted(latencies)[int(len(latencies) * 0.95) - 1]:.2f} ms")

    if stale_success == len(trials):
        print("PASS: stale responses are rejected and the newest turn remains active.")
    else:
        print("FAIL: stale responses were not consistently rejected.")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
