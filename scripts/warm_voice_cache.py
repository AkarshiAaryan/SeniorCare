"""
Script to pre-warm the Rime voice response cache for common senior care conversational states.
Generates Rime TTS audio for canonical responses and populates the persistent voice cache.
"""

import asyncio
import logging
import sys
import os

# Add root directory to python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.voice_prefetcher import voice_prefetcher
from app.services.rime_voice_cache import rime_voice_cache

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("WarmVoiceCache")


async def warm_cache():
    logger.info("Starting Voice Cache Warming...")

    states_to_warm = [
        ("wellness_check", "Friend"),
        ("medication_check", "Friend"),
        ("sleep_inquiry", "Friend"),
        ("pain_check", "Friend"),
        ("emotion_check", "Friend"),
        ("appetite_check", "Friend"),
        ("general_followup", "Friend")
    ]

    total_cached = 0
    for state, name in states_to_warm:
        logger.info(f"Warming top intents for state: '{state}'...")
        entries = await voice_prefetcher.prefetch_for_context(
            context_state=state,
            user_name=name,
            k=3  # Prefetch top 3 intents for each canonical state
        )
        total_cached += len(entries)
        logger.info(f"State '{state}': {len(entries)} items cached.")

    stats = rime_voice_cache.get_stats()
    logger.info("=" * 50)
    logger.info("Voice Cache Warming Complete!")
    logger.info(f"Total Entries Cached on Disk/Memory: {stats['entries_count']}")
    logger.info(f"Total Cached Size: {stats['total_size_bytes']} bytes ({stats['total_size_bytes'] / 1024:.2f} KB)")
    logger.info("=" * 50)


if __name__ == "__main__":
    asyncio.run(warm_cache())
