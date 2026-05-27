"""Voice Activity Detection — wraps webrtcvad with an energy-based fallback."""

import numpy as np
from typing import Callable

# webrtcvad requires PCM at 8/16/32/48 kHz, frames of exactly 10/20/30 ms.
SUPPORTED_RATES = {8000, 16000, 32000, 48000}
FRAME_DURATION_MS = 30


def _bytes_per_frame(sample_rate: int) -> int:
    return int(sample_rate * FRAME_DURATION_MS / 1000) * 2  # int16 = 2 bytes


def create_vad(aggressiveness: int = 2, sample_rate: int = 16000) -> Callable[[bytes], bool]:
    """Return a callable(pcm_bytes) -> bool.  Falls back to energy threshold if
    webrtcvad is unavailable or the sample rate is not supported."""

    if sample_rate not in SUPPORTED_RATES:
        return _energy_vad(threshold=300)

    try:
        try:
            import webrtcvad
        except ImportError:
            import webrtcvad_wheels as webrtcvad  # prebuilt-wheel alias
        vad = webrtcvad.Vad(aggressiveness)
        expected = _bytes_per_frame(sample_rate)

        def _webrtc_fn(pcm_bytes: bytes) -> bool:
            if len(pcm_bytes) != expected:
                return False
            try:
                return vad.is_speech(pcm_bytes, sample_rate)
            except Exception:
                return False

        return _webrtc_fn

    except ImportError:
        return _energy_vad(threshold=300)


def _energy_vad(threshold: int = 300) -> Callable[[bytes], bool]:
    """Simple energy-based fallback when webrtcvad is not installed."""

    def _fn(pcm_bytes: bytes) -> bool:
        if not pcm_bytes:
            return False
        samples = np.frombuffer(pcm_bytes, dtype=np.int16)
        return float(np.abs(samples).mean()) > threshold

    return _fn


def frame_size(sample_rate: int) -> int:
    """Number of int16 samples per VAD frame."""
    return int(sample_rate * FRAME_DURATION_MS / 1000)
