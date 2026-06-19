"""Configuration loader — reads from .env or environment variables."""

import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    groq_api_key: str
    stt_backend: str        # "groq" | "local"
    aider_model: str        # e.g. "groq/llama-3.3-70b-versatile"
    record_mode: str        # "continuous" | "ptt"
    vad_aggressiveness: int
    silence_timeout: float
    sample_rate: int
    device_index: int | None   # None = use system default mic


def load_config() -> Config:
    key = os.getenv("GROQ_API_KEY", "")
    if not key:
        raise EnvironmentError(
            "GROQ_API_KEY is not set.\n"
            "Copy .env.example to .env and add your key from https://console.groq.com"
        )

    vad_aggressiveness = int(os.getenv("VAD_AGGRESSIVENESS", "2"))
    if not (0 <= vad_aggressiveness <= 3):
        raise EnvironmentError(
            f"VAD_AGGRESSIVENESS must be 0–3, got {vad_aggressiveness}.\n"
            "Valid values: 0 (permissive) to 3 (strict)."
        )

    stt_backend = os.getenv("STT_BACKEND", "groq")
    if stt_backend not in ("groq", "local"):
        raise EnvironmentError(
            f"STT_BACKEND must be 'groq' or 'local', got '{stt_backend}'."
        )

    record_mode = os.getenv("RECORD_MODE", "continuous")
    if record_mode not in ("continuous", "ptt"):
        raise EnvironmentError(
            f"RECORD_MODE must be 'continuous' or 'ptt', got '{record_mode}'."
        )

    raw_device = os.getenv("DEVICE_INDEX", "").strip()
    try:
        device_index: int | None = int(raw_device) if raw_device else None
    except ValueError:
        raise EnvironmentError(
            f"DEVICE_INDEX must be an integer, got '{raw_device}'.\n"
            "Run: python -m voice_agent --list-devices  to see valid indices."
        )

    return Config(
        groq_api_key=key,
        stt_backend=stt_backend,
        aider_model=os.getenv("AIDER_MODEL", "groq/llama-3.3-70b-versatile"),
        record_mode=record_mode,
        vad_aggressiveness=vad_aggressiveness,
        silence_timeout=float(os.getenv("SILENCE_TIMEOUT", "1.0")),
        sample_rate=int(os.getenv("SAMPLE_RATE", "16000")),
        device_index=device_index,
    )
