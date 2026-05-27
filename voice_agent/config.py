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


def load_config() -> Config:
    key = os.getenv("GROQ_API_KEY", "")
    if not key:
        raise EnvironmentError(
            "GROQ_API_KEY is not set.\n"
            "Copy .env.example to .env and add your key from https://console.groq.com"
        )
    return Config(
        groq_api_key=key,
        stt_backend=os.getenv("STT_BACKEND", "groq"),
        agent_model=os.getenv("AGENT_MODEL", "llama-3.3-70b-versatile"),
        record_mode=os.getenv("RECORD_MODE", "continuous"),
        vad_aggressiveness=int(os.getenv("VAD_AGGRESSIVENESS", "2")),
        silence_timeout=float(os.getenv("SILENCE_TIMEOUT", "1.5")),
        sample_rate=int(os.getenv("SAMPLE_RATE", "16000")),
    )
