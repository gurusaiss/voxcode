"""Speech-to-Text pipeline.

Primary:  Groq Whisper API  (whisper-large-v3-turbo, free tier, ~200 ms latency)
Fallback: faster-whisper    (local CPU inference, no API needed)
"""

import io
import os
import sys
import tempfile
from typing import Literal


# ── Groq Whisper ──────────────────────────────────────────────────────────────


def transcribe_groq(wav_bytes: bytes, api_key: str) -> str:
    """Send WAV bytes to Groq's Whisper API and return the transcript."""
    from groq import Groq

    client = Groq(api_key=api_key)

    audio_file = io.BytesIO(wav_bytes)
    audio_file.name = "utterance.wav"   # filename signals format to Groq

    response = client.audio.transcriptions.create(
        file=audio_file,
        model="whisper-large-v3-turbo",
        response_format="text",
        language="en",
    )
    return response.strip() if isinstance(response, str) else response.text.strip()


# ── Local Whisper (faster-whisper) ────────────────────────────────────────────

# Module-level cache so the model is loaded only once per process.
_local_model_cache: dict[str, object] = {}


def transcribe_local(
    wav_bytes: bytes,
    model_size: Literal["tiny", "base", "small", "medium"] = "base",
) -> str:
    """Transcribe offline using faster-whisper running on CPU.

    The model is downloaded once and cached in ~/.cache/huggingface.
    Subsequent calls reuse the in-process model — no reload overhead.
    'base' (~140 MB) balances speed and accuracy for developer use.
    """
    try:
        from faster_whisper import WhisperModel
    except ImportError as e:
        raise ImportError(
            "faster-whisper is not installed. "
            "Run: pip install faster-whisper  (or use --stt groq)"
        ) from e

    if model_size not in _local_model_cache:
        _local_model_cache[model_size] = WhisperModel(
            model_size, device="cpu", compute_type="int8"
        )
    model = _local_model_cache[model_size]

    # Write wav bytes to a temp file; faster-whisper requires a file path
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(wav_bytes)
        tmp_path = f.name

    try:
        segments, _ = model.transcribe(tmp_path, language="en", beam_size=1)
        return " ".join(seg.text for seg in segments).strip()
    finally:
        os.unlink(tmp_path)


# ── Dispatcher ────────────────────────────────────────────────────────────────


def transcribe(
    wav_bytes: bytes,
    backend: str = "groq",
    groq_api_key: str = "",
    local_model_size: str = "base",
) -> str:
    """Route to the chosen STT backend.  Falls back to local if Groq fails."""
    if backend == "groq":
        try:
            return transcribe_groq(wav_bytes, groq_api_key)
        except Exception as exc:
            # Graceful fallback — write to stderr so it doesn't break Rich's UI
            print(f"\n[warn] Groq STT failed ({exc}), falling back to local whisper",
                  file=sys.stderr, flush=True)
            return transcribe_local(wav_bytes, local_model_size)

    return transcribe_local(wav_bytes, local_model_size)
