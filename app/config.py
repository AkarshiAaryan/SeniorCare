import os
from dotenv import load_dotenv

# Load environment variables from .env if present
load_dotenv()


class Settings:
    # Rime TTS Settings
    RIME_API_KEY: str = os.getenv("RIME_API_KEY", "")
    RIME_API_URL: str = os.getenv("RIME_API_URL", "https://users.rime.ai/v1/rime-tts")
    RIME_MODEL_ID: str = os.getenv("RIME_MODEL_ID", "coda")  # 'coda' or 'mistv3'
    RIME_SPEAKER: str = os.getenv("RIME_SPEAKER", "celeste")  # Warm, gentle, friendly voice
    # For Coda / Mistv3, timeScaleFactor > 1.0 is slightly slower, ideal for elderly clarity
    RIME_TIME_SCALE_FACTOR: float = float(os.getenv("RIME_TIME_SCALE_FACTOR", "1.05"))
    RIME_AUDIO_FORMAT: str = os.getenv("RIME_AUDIO_FORMAT", "audio/mpeg")

    # LLM / Intelligence Settings
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "gemini-2.5-flash-lite")
    
    # STT Settings
    STT_PROVIDER: str = os.getenv("STT_PROVIDER", "gemini")  # 'gemini', 'openai', 'groq', or 'mock'

    # Predictive Voice-Response Prefetching Settings
    PREFETCH_ENABLED: bool = os.getenv("PREFETCH_ENABLED", "true").lower() in ("true", "1", "yes")
    PREFETCH_TOP_K: int = int(os.getenv("PREFETCH_TOP_K", "2"))
    PREFETCH_CONFIDENCE_THRESHOLD: float = float(os.getenv("PREFETCH_CONFIDENCE_THRESHOLD", "0.75"))
    PREFETCH_CACHE_DIR: str = os.getenv("PREFETCH_CACHE_DIR", ".voice_cache")
    PREFETCH_LOGGING: bool = os.getenv("PREFETCH_LOGGING", "true").lower() in ("true", "1", "yes")


settings = Settings()

