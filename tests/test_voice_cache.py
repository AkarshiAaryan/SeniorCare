import pytest
import os
import shutil
from app.services.rime_voice_cache import RimeVoiceCacheService, compute_rime_cache_key


@pytest.fixture
def temp_cache():
    test_dir = ".test_voice_cache"
    cache = RimeVoiceCacheService(cache_dir=test_dir)
    yield cache
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)


def test_cache_key_generation():
    key1 = compute_rime_cache_key("Hello world", "celeste", "coda", "en", "https://api.rime.ai", "audio/mpeg", 1.05)
    key2 = compute_rime_cache_key("Hello world", "celeste", "coda", "en", "https://api.rime.ai", "audio/mpeg", 1.05)
    key3 = compute_rime_cache_key("Hello world", "other_speaker", "coda", "en", "https://api.rime.ai", "audio/mpeg", 1.05)

    assert key1 == key2
    assert key1 != key3
    assert len(key1) == 64  # SHA-256


def test_put_get_cache(temp_cache):
    fake_audio = b"FAKE_AUDIO_DATA_FOR_TESTING"
    cfg = {"speaker": "celeste", "model_id": "coda", "speed": 1.05}

    entry = temp_cache.put(
        context_state="wellness_check",
        intent="mood_positive",
        text="That's wonderful to hear!",
        audio_bytes=fake_audio,
        rime_config=cfg
    )

    assert entry is not None
    assert entry.text == "That's wonderful to hear!"

    # Retrieve from cache
    cached = temp_cache.get("wellness_check", "mood_positive", cfg)
    assert cached is not None
    assert cached.audio_bytes == fake_audio
    assert cached.text == "That's wonderful to hear!"

    # Test context isolation: requesting different intent or state should be cache miss
    assert temp_cache.get("wellness_check", "mood_negative", cfg) is None
    assert temp_cache.get("medication_check", "mood_positive", cfg) is None


def test_cache_stats_and_clearing(temp_cache):
    fake_audio = b"SAMPLE_AUDIO_123"
    cfg = {"speaker": "celeste", "model_id": "coda", "speed": 1.05}

    temp_cache.put("sleep_inquiry", "sleep_good", "Glad you slept well!", fake_audio, cfg)
    
    # Hit
    hit = temp_cache.get("sleep_inquiry", "sleep_good", cfg)
    assert hit is not None

    # Miss
    miss = temp_cache.get("sleep_inquiry", "sleep_bad", cfg)
    assert miss is None

    stats = temp_cache.get_stats()
    assert stats["hits"] >= 1
    assert stats["misses"] >= 1
    assert stats["entries_count"] == 1

    # Clear
    temp_cache.clear()
    assert temp_cache.get_stats()["entries_count"] == 0
