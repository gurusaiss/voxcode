# VoxCode — Voice Interface for aider

> **Hands-free voice input layer for [aider](https://github.com/paul-gauthier/aider), the open-source terminal coding agent.**
> Speak naturally — your words are transcribed by Groq Whisper and forwarded to aider as queries. Aider handles all code editing and displays responses on screen. No mouse. Minimal keyboard.

---

## Demo setup time

**Under 3 minutes** (install deps + paste API key).
Pre-installed environments: **under 60 seconds**.

---

## What it does

```
You speak  →  Groq Whisper transcribes (~200 ms)  →  aider receives the text
                                                    →  aider edits files, streams response
You speak  →  ...
```

The voice interface provides the **input layer only**. aider owns all LLM interaction, code editing, diff display, and git integration — exactly as it would in a normal terminal session. The only difference is that your words arrive by voice instead of keyboard.

---

## What it looks like

```
╭─ VOICE INTERFACE FOR AIDER ─────────────────────────────────────────╮
│   voice-driven input layer  |  Groq STT                             │
│   model: groq/llama-3.3-70b-versatile  |  mode: continuous          │
╰─────────────────────────────────────────────────────────────────────╯

* Listening...  (speak naturally — pause to send to aider)

* REC    ........................................    12 rms   <- waiting (red)
* HEARD  ###########################.............   847 rms   <- speech detected (green)

                    Transcribing speech...   <- Groq Whisper spinner (~200 ms)

╭─ You  (turn 3) ────────────────────────────────────────────────────╮
│  Add error handling so balance can't go negative                   │
╰────────────────────────────────────────────────────────────────────╯
  ↳ aider

<aider renders its own response, diffs, and file edits here>
```

---

## Requirements

- **Python 3.10+**
- **A microphone** (any built-in or USB mic)
- **Groq API key** — free at [console.groq.com](https://console.groq.com) (no credit card)
- **Git** — aider works best inside a git repository

---

## Installation

```bash
# 1. Enter your project directory (git repo)
cd your-project

# 2. Extract voxcode and install
pip install -r /path/to/voxcode/requirements.txt

# 3. Add your API key
cp .env.example .env
# Open .env and set: GROQ_API_KEY=gsk_...your_key_here...
```

> **Note:** `aider-chat` is included in `requirements.txt` and installed automatically.  
> A git repository is recommended — run `git init` if your project directory isn't one yet.

---

## Running

```bash
# Default — continuous VAD mode (fully hands-free)
python -m voice_agent

# Push-to-talk — hold SPACE to record, release to send
python -m voice_agent --mode ptt

# Use local offline STT (no internet needed for transcription)
python -m voice_agent --stt local

# List microphone devices (if default mic is wrong)
python -m voice_agent --list-devices

# Show all voice macros
python -m voice_agent --help-macros

# Use a different model (any litellm-compatible model string)
python -m voice_agent --model claude-3-5-sonnet-20241022
python -m voice_agent --model gpt-4o
```

**First run walkthrough:**
1. `cd` into your project directory (git repo)
2. Run `python -m voice_agent`
3. aider initialises, the banner and help panel appear
4. You see `* Listening...` — start speaking
5. Pause for ~1 second → recording stops automatically
6. A spinner shows `Transcribing...` (~200 ms)
7. Your words are forwarded to aider — aider responds as normal
8. The system loops back to listening

No key presses needed between turns.

---

## Voice macros

Voice macros map natural spoken phrases to aider's built-in slash commands. All are forwarded to `aider.run()` — aider handles them natively.

| Say this | Sends to aider | Effect |
|---|---|---|
| "exit" / "quit" / "goodbye" | *(exits the voice loop)* | End session |
| "undo" / "undo that" | `/undo` | Undo last aider edit |
| "clear" / "start over" | `/clear` | Clear conversation context |
| "show files" / "list files" | `/ls` | List files in aider's context |
| "show diff" / "what changed" | `/diff` | Show uncommitted changes |
| "commit" / "commit changes" | `/commit` | Commit current edits to git |
| "add main.py" | `/add main.py` | Add file to aider's context |
| "drop utils.py" | `/drop utils.py` | Remove file from context |
| "help" / "show commands" | `/help` | Show aider's help |

All other spoken text is forwarded to aider as a natural-language coding request.

---

## Hands-free coverage

| Interaction | Hands-free? | Notes |
|---|---|---|
| Coding requests | ✅ 100% | Speak naturally to aider |
| File edits | ✅ 100% | aider applies changes directly |
| Add/drop files in context | ✅ 100% | "add main.py" |
| Undo edits | ✅ 100% | "undo that" |
| View diff | ✅ 100% | "show diff" |
| Commit to git | ✅ 100% | "commit" |
| Reset context | ✅ 100% | "clear" |
| Exit session | ✅ 100% | "exit" |
| Start the program | ⚠️ One command | `python -m voice_agent` |
| Stop (fallback) | ⚠️ Ctrl+C | Only if voice exit fails |

---

## Architecture

```
Microphone (sounddevice)
      |
      | 30 ms PCM frames @ 16 kHz
      v
VAD (webrtcvad / energy fallback)
      |
      | speech detected? accumulate frames
      | silence for 1.0 s? → flush buffer
      v
WAV bytes (in-memory, never written to disk)
      |
      v
STT dispatcher (transcribe.py)
      |--- backend=groq  --> Groq Whisper API (whisper-large-v3-turbo)  ~200 ms
      |--- backend=local --> faster-whisper (local CPU, base model)     ~1-2 s
      |
      v
Plain text transcription
      |
      v
Voice macro resolver (commands.py)
      |--- known phrase? --> aider slash command (/undo, /clear, /add <f>, ...)
      |--- unknown?      --> text passes through unchanged
      |
      v
AiderBridge.run(text)  [aider_bridge.py]
      |
      v
aider Coder.run(text)  ← aider takes over from here
      |--- sends to LLM (groq/llama-3.3-70b-versatile via litellm)
      |--- applies file edits
      |--- renders response, diffs, confirmations to terminal
      |
      v
Loop back to microphone
```

The voice interface is a pure input layer. It has no knowledge of code, files, or LLM responses — that is aider's job.

---

## Configuration (`.env`)

| Variable | Default | Description |
|---|---|---|
| `GROQ_API_KEY` | *(required)* | Your Groq API key — used for STT and aider LLM |
| `STT_BACKEND` | `groq` | `groq` (Whisper API) or `local` (faster-whisper) |
| `AIDER_MODEL` | `groq/llama-3.3-70b-versatile` | Any litellm model string |
| `RECORD_MODE` | `continuous` | `continuous` (VAD) or `ptt` (push-to-talk) |
| `VAD_AGGRESSIVENESS` | `2` | 0 = permissive → 3 = strict |
| `SILENCE_TIMEOUT` | `1.0` | Seconds of post-speech silence before sending |
| `SAMPLE_RATE` | `16000` | Microphone sample rate in Hz |
| `DEVICE_INDEX` | *(system default)* | Mic device number — see `--list-devices` |

### Using a different LLM

aider supports any litellm-compatible model. Set `AIDER_MODEL` in `.env` and provide the matching API key:

```bash
# Anthropic Claude (needs ANTHROPIC_API_KEY)
AIDER_MODEL=claude-3-5-sonnet-20241022

# OpenAI GPT-4o (needs OPENAI_API_KEY)
AIDER_MODEL=gpt-4o

# Groq (default, free tier, needs GROQ_API_KEY)
AIDER_MODEL=groq/llama-3.3-70b-versatile
```

---

## Offline / no-API STT

```bash
pip install faster-whisper
```

Set in `.env`:
```
STT_BACKEND=local
```

STT now runs fully locally (~1–2 s latency). The aider LLM still calls the API — there is no free locally-runnable model at `llama-3.3-70b-versatile` quality, but `faster-whisper` makes transcription free and offline.

---

## Running tests

```bash
pip install pytest
pytest tests/ -v
```

Tests use mocked APIs — **no microphone, no API key required**.

---

## Cost

**$0 with default settings.** Groq's free tier provides:
- **7,200 minutes/day** of Whisper audio transcription
- **500,000 tokens/minute** on `llama-3.3-70b-versatile`

A typical 15-turn demo session uses ~4 minutes of audio and ~6,000 tokens — well under 0.1% of the daily free allowance.

---

## Project structure

```
voxcode/
├── voice_agent/
│   ├── __main__.py          # Enables `python -m voice_agent`
│   ├── main.py              # CLI definition and session loop
│   ├── config.py            # .env loader, Config dataclass
│   ├── audio/
│   │   ├── capture.py       # Microphone recording + VAD auto-stop
│   │   ├── vad.py           # webrtcvad wrapper + energy fallback
│   │   └── transcribe.py    # STT dispatcher — Groq Whisper or faster-whisper
│   ├── agent/
│   │   ├── aider_bridge.py  # Wraps aider's Python API (Coder.run)
│   │   └── commands.py      # Voice macro → aider slash command resolver
│   └── ui/
│       └── display.py       # Rich terminal UI — waveform, transcription panel
├── tests/
│   ├── test_audio.py        # VAD, frame size, WAV encoding
│   └── test_transcribe.py   # STT dispatch, macro resolution
├── .env.example
├── .gitignore
├── requirements.txt
├── setup.py
├── LICENSE
├── README.md
└── REPORT.md
```

---

## Troubleshooting

**`No module named sounddevice`**
→ `pip install sounddevice`

**`PortAudio not found` on Linux**
→ `sudo apt install portaudio19-dev` then `pip install sounddevice`

**aider says "No git repo found"**
→ Run `git init` in your project directory. aider works without git but warns.

**Groq API key error at startup**
→ Ensure `.env` exists and contains a valid `GROQ_API_KEY=gsk_...`

**Wrong microphone selected**
→ `python -m voice_agent --list-devices` then set `DEVICE_INDEX=<number>` in `.env`

**VAD triggers on background noise**
→ Increase `VAD_AGGRESSIVENESS=3` in `.env`, or use `--mode ptt`

---

## License

MIT — see [LICENSE](LICENSE).
