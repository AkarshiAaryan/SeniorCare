"""
Rime Voice Cache Module for SeniorCare
Persistent disk and in-memory audio cache with strict configuration hashing and context isolation.
"""

import os
import json
import base64
import hashlib
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from dataclasses import dataclass, asdict

from app.config import settings

logger = logging.getLogger("RimeVoiceCache")


@dataclass
class CachedAudioEntry:
    response_id: str
    context_state: str
    intent: str
    text: str
    voice: str
    model: str
    language: str
    endpoint: str
    audio_format: str
    speed: float
    cache_key: str
    audio_base64: str
    audio_path: Optional[str] = None
    created_at: str = ""

    @property
    def audio_bytes(self) -> bytes:
        return base64.b64decode(self.audio_base64)


def compute_rime_cache_key(
    text: str,
    voice: str,
    model: str,
    language: str,
    endpoint: str,
    audio_format: str,
    speed: float
) -> str:
    """
    Generates deterministic SHA-256 key from complete Rime generation configuration.
    """
    norm_text = text.strip()
    speed_str = f"{float(speed):.3f}"
    payload = f"{norm_text}|{model}|{voice}|{language}|{endpoint}|{audio_format}|{speed_str}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class RimeVoiceCacheService:
    def __init__(self, cache_dir: Optional[str] = None):
        self.cache_dir = cache_dir or getattr(settings, "PREFETCH_CACHE_DIR", ".voice_cache")
        self._memory_cache: Dict[str, CachedAudioEntry] = {}
        # Context + Intent index: (context_state, intent) -> cache_key
        self._context_intent_index: Dict[str, str] = {}
        self.hits = 0
        self.misses = 0

        self._init_storage()

    def _init_storage(self) -> None:
        """
        Initializes disk directory and loads existing metadata.
        """
        try:
            os.makedirs(self.cache_dir, exist_ok=True)
            meta_path = os.path.join(self.cache_dir, "metadata.json")
            if os.path.exists(meta_path):
                with open(meta_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data.values():
                        entry = CachedAudioEntry(**item)
                        # Load audio file if not present in memory
                        if not entry.audio_base64 and entry.audio_path and os.path.exists(entry.audio_path):
                            with open(entry.audio_path, "rb") as af:
                                entry.audio_base64 = base64.b64encode(af.read()).decode("utf-8")
                        self._memory_cache[entry.cache_key] = entry
                        idx_key = f"{entry.context_state}:{entry.intent}"
                        self._context_intent_index[idx_key] = entry.cache_key
        except Exception as e:
            logger.warning(f"Failed to load voice cache from disk: {e}")

    def _save_metadata(self) -> None:
        """
        Persists in-memory cache metadata to disk.
        """
        try:
            os.makedirs(self.cache_dir, exist_ok=True)
            meta_path = os.path.join(self.cache_dir, "metadata.json")
            data = {}
            for k, v in self._memory_cache.items():
                item_dict = asdict(v)
                # Omit base64 from metadata JSON to keep it light
                item_dict["audio_base64"] = ""
                data[k] = item_dict
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to persist voice cache metadata: {e}")

    def compute_cache_key(
        self,
        text: str,
        model: str,
        voice: str,
        language: str,
        endpoint: str,
        audio_format: str,
        speed: float
    ) -> str:
        """
        Generates deterministic SHA-256 key from complete Rime generation configuration.
        """
        return compute_rime_cache_key(
            text=text,
            voice=voice,
            model=model,
            language=language,
            endpoint=endpoint,
            audio_format=audio_format,
            speed=speed
        )

    def get(
        self,
        context_state: str,
        intent: str,
        rime_config: Optional[Dict[str, Any]] = None
    ) -> Optional[CachedAudioEntry]:
        """
        Context-aware cache lookup. Returns matching entry only if:
        1. Context state and intent match.
        2. Rime configuration matches the exact computed key.
        """
        idx_key = f"{context_state}:{intent}"
        cache_key = self._context_intent_index.get(idx_key)

        if not cache_key:
            self.misses += 1
            return None

        entry = self._memory_cache.get(cache_key)
        if not entry:
            self.misses += 1
            return None

        # Verify Rime config consistency if provided
        if rime_config:
            expected_key = self.compute_cache_key(
                text=entry.text,
                model=rime_config.get("model_id", entry.model),
                voice=rime_config.get("speaker", entry.voice),
                language=rime_config.get("language", entry.language),
                endpoint=rime_config.get("endpoint", entry.endpoint),
                audio_format=rime_config.get("audio_format", entry.audio_format),
                speed=rime_config.get("speed", entry.speed)
            )
            if expected_key != cache_key:
                logger.info(f"Cache key mismatch for {idx_key} due to Rime config change. Miss.")
                self.misses += 1
                return None

        self.hits += 1
        return entry

    def get_by_key(self, cache_key: str) -> Optional[CachedAudioEntry]:
        """
        Direct lookup by SHA-256 cache key.
        """
        entry = self._memory_cache.get(cache_key)
        if entry:
            self.hits += 1
            return entry
        self.misses += 1
        return None

    def put(
        self,
        context_state: str,
        intent: str,
        text: str,
        audio_bytes: bytes,
        rime_config: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> CachedAudioEntry:
        """
        Stores synthesized audio into memory and disk cache.
        """
        cfg = rime_config or {}
        model = cfg.get("model_id", getattr(settings, "RIME_MODEL_ID", "coda"))
        voice = cfg.get("speaker", getattr(settings, "RIME_SPEAKER", "celeste"))
        speed = float(cfg.get("speed", getattr(settings, "RIME_TIME_SCALE_FACTOR", 1.05)))
        language = cfg.get("language", "en")
        endpoint = cfg.get("endpoint", getattr(settings, "RIME_API_URL", "https://users.rime.ai/v1/rime-tts"))
        audio_format = cfg.get("audio_format", getattr(settings, "RIME_AUDIO_FORMAT", "audio/mpeg"))

        cache_key = self.compute_cache_key(
            text=text,
            model=model,
            voice=voice,
            language=language,
            endpoint=endpoint,
            audio_format=audio_format,
            speed=speed
        )

        audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
        audio_filename = f"{cache_key}.mp3"
        audio_path = os.path.join(self.cache_dir, audio_filename)

        try:
            with open(audio_path, "wb") as f:
                f.write(audio_bytes)
        except Exception as e:
            logger.warning(f"Could not write audio to disk {audio_path}: {e}")

        response_id = (metadata or {}).get("response_id", f"{context_state}__{intent}")
        created_at = datetime.utcnow().isoformat()

        entry = CachedAudioEntry(
            response_id=response_id,
            context_state=context_state,
            intent=intent,
            text=text,
            voice=voice,
            model=model,
            language=language,
            endpoint=endpoint,
            audio_format=audio_format,
            speed=speed,
            cache_key=cache_key,
            audio_base64=audio_b64,
            audio_path=audio_path,
            created_at=created_at
        )

        self._memory_cache[cache_key] = entry
        idx_key = f"{context_state}:{intent}"
        self._context_intent_index[idx_key] = cache_key

        self._save_metadata()
        return entry

    def invalidate_context(self, context_state: str) -> None:
        """
        Invalidates all cache entries for a specific conversational context.
        """
        keys_to_remove = []
        for idx_key, cache_key in list(self._context_intent_index.items()):
            if idx_key.startswith(f"{context_state}:"):
                keys_to_remove.append(idx_key)
                self._memory_cache.pop(cache_key, None)

        for k in keys_to_remove:
            self._context_intent_index.pop(k, None)

        self._save_metadata()

    def clear(self) -> None:
        """
        Clears all in-memory and disk cache entries.
        """
        self._memory_cache.clear()
        self._context_intent_index.clear()
        self.hits = 0
        self.misses = 0
        try:
            meta_path = os.path.join(self.cache_dir, "metadata.json")
            if os.path.exists(meta_path):
                os.remove(meta_path)
        except Exception as e:
            logger.warning(f"Failed to delete metadata file on clear: {e}")

    def stats(self) -> Dict[str, Any]:
        """
        Returns performance and capacity statistics of the voice cache.
        """
        total = self.hits + self.misses
        rate = (self.hits / total) if total > 0 else 0.0
        size_bytes = sum(len(e.audio_base64) for e in self._memory_cache.values())
        return {
            "total_entries": len(self._memory_cache),
            "entries_count": len(self._memory_cache),
            "total_size_bytes": size_bytes,
            "hits": self.hits,
            "misses": self.misses,
            "total_lookups": total,
            "hit_rate": round(rate, 4),
            "hit_rate_percent": round(rate * 100, 2),
            "cache_dir": self.cache_dir
        }

    def get_stats(self) -> Dict[str, Any]:
        return self.stats()


rime_voice_cache = RimeVoiceCacheService()
