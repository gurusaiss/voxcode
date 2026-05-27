"""Microphone capture — records audio until silence is detected (VAD) or a
timeout is reached.  Returns raw WAV bytes ready for the STT pipeline."""

import io
import wave
import threading
import numpy as np
import sounddevice as sd
from typing import Callable, Optional

from voice_agent.audio.vad import create_vad, frame_size

# ── constants ────────────────────────────────────────────────────────────────

CHANNELS = 1
DTYPE = np.int16

# ── recording helpers ─────────────────────────────────────────────────────────


def _to_wav_bytes(samples: np.ndarray, sample_rate: int) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(2)        # int16 = 2 bytes
        wf.setframerate(sample_rate)
        wf.writeframes(samples.tobytes())
    return buf.getvalue()


# ── public API ────────────────────────────────────────────────────────────────


def record_continuous(
    sample_rate: int = 16000,
    silence_timeout: float = 1.0,
    vad_aggressiveness: int = 2,
    on_energy: Optional[Callable[[float], None]] = None,
    on_speech_start: Optional[Callable[[], None]] = None,
    max_duration: float = 30.0,
    device: Optional[int] = None,
) -> Optional[bytes]:
    """Block until the user speaks, then record until silence.

    Args:
        sample_rate:        Mic sample rate (Hz).
        silence_timeout:    Seconds of post-speech silence that end the utterance.
        vad_aggressiveness: webrtcvad aggressiveness 0–3.
        on_energy:          Callback(rms_float) called every 30 ms frame for UI.
        on_speech_start:    Callback() fired the instant speech is first detected.
        max_duration:       Hard cut-off in seconds — prevents infinite loops.

    Returns:
        WAV bytes of the recorded utterance, or None if nothing was captured.
    """
    is_speech = create_vad(vad_aggressiveness, sample_rate)
    fsize = frame_size(sample_rate)           # samples per frame (30 ms)
    frames_per_second = sample_rate / fsize
    silence_frames_needed = int(silence_timeout * frames_per_second)
    max_frames = int(max_duration * frames_per_second)

    buffer: list[np.ndarray] = []
    speech_started = False
    silent_frame_count = 0
    total_frames = 0

    with sd.InputStream(samplerate=sample_rate, channels=CHANNELS, dtype=DTYPE,
                        device=device) as stream:
        while total_frames < max_frames:
            chunk, _ = stream.read(fsize)
            chunk = chunk[:, 0]  # mono
            total_frames += 1

            rms = float(np.sqrt(np.mean(chunk.astype(np.float32) ** 2)))
            if on_energy:
                on_energy(rms)

            speaking = is_speech(chunk.tobytes())

            if speaking:
                if not speech_started and on_speech_start:
                    on_speech_start()           # notify UI immediately
                buffer.append(chunk.copy())
                speech_started = True
                silent_frame_count = 0
            elif speech_started:
                buffer.append(chunk.copy())   # keep trailing silence for natural endings
                silent_frame_count += 1
                if silent_frame_count >= silence_frames_needed:
                    break
            # if no speech yet, keep looping (waiting for user to start)

    if not buffer:
        return None

    audio = np.concatenate(buffer)
    return _to_wav_bytes(audio, sample_rate)


def record_push_to_talk(
    sample_rate: int = 16000,
    on_energy: Optional[Callable[[float], None]] = None,
) -> Optional[bytes]:
    """Record while the user holds SPACE, stop on release.

    Falls back gracefully if pynput is unavailable.
    """
    try:
        from pynput import keyboard as kb
    except ImportError:
        return None

    stop_event = threading.Event()
    start_event = threading.Event()
    buffer: list[np.ndarray] = []
    fsize = frame_size(sample_rate)

    def on_press(key):
        if key == kb.Key.space:
            start_event.set()

    def on_release(key):
        if key == kb.Key.space:
            stop_event.set()
            return False  # stop listener

    listener = kb.Listener(on_press=on_press, on_release=on_release)
    listener.start()

    # Wait for spacebar press
    start_event.wait(timeout=60)

    with sd.InputStream(samplerate=sample_rate, channels=CHANNELS, dtype=DTYPE) as stream:
        while not stop_event.is_set():
            chunk, _ = stream.read(fsize)
            chunk = chunk[:, 0]
            buffer.append(chunk.copy())
            if on_energy:
                rms = float(np.sqrt(np.mean(chunk.astype(np.float32) ** 2)))
                on_energy(rms)

    listener.join()

    if not buffer:
        return None

    audio = np.concatenate(buffer)
    return _to_wav_bytes(audio, sample_rate)


def list_devices() -> str:
    """Return a formatted string of available audio input devices."""
    devices = sd.query_devices()
    lines = []
    for i, d in enumerate(devices):
        if d["max_input_channels"] > 0:
            marker = " (default)" if i == sd.default.device[0] else ""
            lines.append(f"  [{i}] {d['name']}{marker}")
    return "\n".join(lines) if lines else "  No input devices found."
