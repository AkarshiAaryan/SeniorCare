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
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "gemini-3.6-flash")
    
    # STT Settings
    STT_PROVIDER: str = os.getenv("STT_PROVIDER", "gemini")  # 'gemini', 'openai', 'groq', or 'mock'

    # Notification settings
    NOTIFY_CHANNELS: str = os.getenv("NOTIFY_CHANNELS", "email")  # comma-separated: email,sms,push
    SMTP_HOST: str = os.getenv("SMTP_HOST", "")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASS: str = os.getenv("SMTP_PASS", "")
    SENDER_EMAIL: str = os.getenv("SENDER_EMAIL", "no-reply@seniorcare.local")
    TWILIO_SID: str = os.getenv("TWILIO_SID", "")
    TWILIO_TOKEN: str = os.getenv("TWILIO_TOKEN", "")
    TWILIO_FROM: str = os.getenv("TWILIO_FROM", "")
    NOTIFY_ADMIN_EMAIL: str = os.getenv("NOTIFY_ADMIN_EMAIL", "")


settings = Settings()
