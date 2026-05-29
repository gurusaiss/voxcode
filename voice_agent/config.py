"""Configuration loader — reads from .env or environment variables."""

import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    groq_api_key: str
    stt_backend: str        # "groq" | "local"
    agent_model: str
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
    raw_device = os.getenv("DEVICE_INDEX", "").strip()
    vad_aggressiveness = int(os.getenv("VAD_AGGRESSIVENESS", "2"))
    if not (0 <= vad_aggressiveness <= 3):
        raise EnvironmentError(
            f"VAD_AGGRESSIVENESS must be 0–3, got {vad_aggressiveness}.\n"
            "Valid values: 0 (permissive) to 3 (strict)."
        )
    return Config(
        groq_api_key=key,
        stt_backend=os.getenv("STT_BACKEND", "groq"),
        agent_model=os.getenv("AGENT_MODEL", "llama-3.3-70b-versatile"),
        record_mode=os.getenv("RECORD_MODE", "continuous"),
        vad_aggressiveness=vad_aggressiveness,
        silence_timeout=float(os.getenv("SILENCE_TIMEOUT", "1.0")),
        sample_rate=int(os.getenv("SAMPLE_RATE", "16000")),
        device_index=int(raw_device) if raw_device.isdigit() else None,
    )
