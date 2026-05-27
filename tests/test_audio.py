"""Unit tests for the audio pipeline (no microphone required)."""

import io
import wave
import struct
import math
import numpy as np
import pytest

from voice_agent.audio.vad import create_vad, frame_size, _energy_vad
from voice_agent.audio.capture import _to_wav_bytes


# ── helpers ───────────────────────────────────────────────────────────────────


def _sine_wave_pcm(freq_hz: int = 440, duration_ms: int = 30, sample_rate: int = 16000) -> bytes:
    """Generate a pure sine wave as raw int16 PCM bytes."""
    n_samples = int(sample_rate * duration_ms / 1000)
    samples = [
        int(32767 * math.sin(2 * math.pi * freq_hz * i / sample_rate))
        for i in range(n_samples)
    ]
    return struct.pack(f"<{n_samples}h", *samples)


def _silence_pcm(duration_ms: int = 30, sample_rate: int = 16000) -> bytes:
    n_samples = int(sample_rate * duration_ms / 1000)
    return bytes(n_samples * 2)


# ── VAD tests ─────────────────────────────────────────────────────────────────


class TestEnergyVAD:
    def test_silence_not_speech(self):
        vad = _energy_vad(threshold=300)
        assert vad(_silence_pcm()) is False

    def test_loud_signal_is_speech(self):
        vad = _energy_vad(threshold=300)
        assert vad(_sine_wave_pcm()) is True

    def test_empty_bytes_not_speech(self):
        vad = _energy_vad(threshold=300)
        assert vad(b"") is False


class TestCreateVAD:
    def test_returns_callable(self):
        vad = create_vad(aggressiveness=2, sample_rate=16000)
        assert callable(vad)

    def test_unsupported_sample_rate_falls_back(self):
        # 22050 is not a webrtcvad-supported rate → falls back to energy VAD
        vad = create_vad(aggressiveness=2, sample_rate=22050)
        assert callable(vad)
        # Should not raise even with arbitrary bytes
        result = vad(_sine_wave_pcm(sample_rate=22050))
        assert isinstance(result, bool)

    def test_frame_size_correct(self):
        # 30 ms at 16 kHz = 480 samples
        assert frame_size(16000) == 480
        assert frame_size(8000) == 240


# ── WAV encoding tests ────────────────────────────────────────────────────────


class TestToWavBytes:
    def test_output_is_valid_wav(self):
        samples = np.zeros(16000, dtype=np.int16)
        wav_bytes = _to_wav_bytes(samples, 16000)

        buf = io.BytesIO(wav_bytes)
        with wave.open(buf, "rb") as wf:
            assert wf.getnchannels() == 1
            assert wf.getsampwidth() == 2
            assert wf.getframerate() == 16000
            assert wf.getnframes() == 16000

    def test_sine_wave_roundtrip(self):
        pcm = _sine_wave_pcm(duration_ms=100)
        samples = np.frombuffer(pcm, dtype=np.int16)
        wav_bytes = _to_wav_bytes(samples, 16000)
        assert len(wav_bytes) > len(pcm)  # WAV header overhead

    def test_empty_audio_produces_valid_wav(self):
        samples = np.array([], dtype=np.int16)
        wav_bytes = _to_wav_bytes(samples, 16000)
        buf = io.BytesIO(wav_bytes)
        with wave.open(buf, "rb") as wf:
            assert wf.getnframes() == 0
