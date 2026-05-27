# Voice Terminal Agent

> **A fully hands-free voice interface for a terminal AI coding agent.**  
> Speak naturally — your words are transcribed and sent to a Groq-powered coding agent in real time. Responses stream directly to the terminal. No mouse required. Minimal keyboard interaction.

---

## Demo setup time

**Under 2 minutes** (install deps + paste API key).  
Pre-installed environments: **under 30 seconds**.

---

## What it looks like

```
╭────────────────────────────────────────────────────────────────╮
│   VOICE CODING AGENT  |  voice-driven terminal AI  |  Groq    │
│        model: llama-3.3-70b-versatile  |  mode: continuous    │
╰────────────────────────────────────────────────────────────────╯

╭─ Help ─────────────────────────────────────────────────────────╮
│ Keyboard shortcuts                                             │
│   Ctrl+C  - exit session                                       │
│                                                                │
│ Voice macros                                                   │
│   /exit    -> "exit", "quit", "goodbye"                       │
│   /undo    -> "undo", "undo that", "revert"                   │
│   /clear   -> "clear", "reset", "start over"                  │
│   /files   -> "show files", "list files"                      │
│   /help    -> "help", "what can you do"                       │
╰────────────────────────────────────────────────────────────────╯

* Listening...  (speak naturally - pause to send)

* REC    ........................................   12 rms   <- waiting (red)
* HEARD  ###########################.............  847 rms   <- speech detected (green)

                    Transcribing speech...   <- spinner (~200 ms)

╭─ You  (turn 3) ────────────────────────────────────────────────╮
│  Add error handling so balance can't go negative               │
╰────────────────────────────────────────────────────────────────╯

──────────────────────────── Agent ─────────────────────────────
Here's the updated `BankAccount` class with balance validation:

```python
class BankAccount:
    def __init__(self, owner: str, balance: float = 0.0):
        self._balance = balance
        self.owner = owner

    def withdraw(self, amount: float) -> None:
        if amount > self._balance:
            raise ValueError(
                f"Insufficient funds: balance is {self._balance}"
            )
        self._balance -= amount
```

The `withdraw` method now raises `ValueError` before deducting.
────────────────────────────────────────────────────────────────
```

---

## Requirements

- **Python 3.10+**
- **A microphone** (any built-in or USB mic)
- **Groq API key** — free at [console.groq.com](https://console.groq.com) (no credit card)

---

## Installation

```bash
# 1. Extract the project and enter the directory
cd voice-terminal-agent

# 2. Create a virtual environment (recommended)
python -m venv .venv

# Activate — Windows
.venv\Scripts\activate

# Activate — macOS / Linux
source .venv/bin/activate

# 3. Install all dependencies
pip install -r requirements.txt

# 4. Add your API key
cp .env.example .env
# Open .env and set: GROQ_API_KEY=gsk_...your_key_here...
```

That's it. No dataset downloads, no model weights to fetch, no database setup.

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

# Print all voice macros and exit
python -m voice_agent --help-macros

# Use a different Groq model
python -m voice_agent --model llama-3.1-8b-instant
```

**First run walkthrough:**
1. Run `python -m voice_agent`
2. The banner and help panel appear
3. You see `* Listening...` — start speaking
4. Pause for ~1.5 seconds → recording stops automatically
5. A spinner shows `Transcribing...` (~200 ms)
6. The agent response streams to the terminal immediately
7. The system loops back to listening

No key presses needed between turns.

---

## Voice macros — the hands-free layer

Every essential session action is accessible by voice. Macro matching is case-insensitive and tolerates trailing punctuation.

| Say this | Sends | Effect |
|---|---|---|
| "exit" / "quit" / "goodbye" | `/exit` | End session cleanly |
| "undo" / "undo that" / "revert" | `/undo` | Remove last exchange from context |
| "clear" / "reset" / "start over" | `/clear` | Reset conversation history |
| "save that" / "write to file" | `/save` | **Save last code block to disk** (auto-named) |
| "save that as main.py" | `/save main.py` | **Save with a specific filename** |
| "run that" / "run the code" | `/run` | **Execute the last saved file** |
| "show directory" / "list directory" | `/ls` | List current directory contents |
| "show files" / "list files" | `/files` | List filenames mentioned in session |
| "help" / "what can you do" | `/help` | Show all commands |
| "show history" | `/history` | Summarise the session so far |

### The complete hands-free coding loop

```
You say:  "Write a function that reads a CSV file and prints the first 5 rows"
Agent:    streams Python code to terminal

You say:  "Save that as read_csv.py"
Agent:    [Saved] Code written to read_csv.py  (12 lines)

You say:  "Run that"
Agent:    [Run] read_csv.py (exit code 0)
          name, age, city
          Alice, 30, London
          ...

You say:  "Add error handling if the file doesn't exist"
Agent:    streams updated code

You say:  "Save that as read_csv.py"
          "Run that"
          "Exit"
```

**Zero keyboard. Zero mouse. End to end.**

---

## Hands-free coverage

| Interaction | Hands-free? | Notes |
|---|---|---|
| Coding requests | ✅ 100% | Speak naturally |
| Save code to disk | ✅ 100% | "save that" / "save as main.py" |
| Run saved code | ✅ 100% | "run that" |
| List directory | ✅ 100% | "show directory" |
| Undo last turn | ✅ 100% | "undo that" |
| Reset session | ✅ 100% | "clear" |
| Exit session | ✅ 100% | "exit" |
| Start the program | ⚠️ One command | `python -m voice_agent` |
| Stop (fallback) | ⚠️ Ctrl+C | Only if voice exit fails |

**In continuous VAD mode:** once the program is running, zero keyboard input is required. The entire edit → save → run → iterate cycle is voice-controlled.

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
      | silence for 1.5 s? → flush buffer
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
      |--- known phrase? --> slash command (/undo, /clear, /exit, ...)
      |--- unknown?      --> text passes through unchanged
      |
      v
GroqAgent (groq_agent.py)
      |--- slash command? --> handle locally, no LLM call
      |--- text query?    --> Groq chat completion (streaming)
      |
      | token stream
      v
Rich terminal renderer (display.py)
      |
      v
Loop back to microphone
```

Each stage is a standalone module. The audio pipeline has no knowledge of the agent. The agent has no knowledge of audio. This makes each stage independently testable and swappable.

---

## Configuration (`.env`)

Copy `.env.example` to `.env` and edit:

| Variable | Default | Description |
|---|---|---|
| `GROQ_API_KEY` | *(required)* | Your Groq API key |
| `STT_BACKEND` | `groq` | `groq` (Whisper API) or `local` (faster-whisper) |
| `AGENT_MODEL` | `llama-3.3-70b-versatile` | Any Groq-hosted chat model |
| `RECORD_MODE` | `continuous` | `continuous` (VAD) or `ptt` (push-to-talk) |
| `VAD_AGGRESSIVENESS` | `2` | 0 = permissive → 3 = strict |
| `SILENCE_TIMEOUT` | `1.0` | Seconds of post-speech silence before sending |
| `SAMPLE_RATE` | `16000` | Microphone sample rate in Hz |
| `DEVICE_INDEX` | *(system default)* | Mic device number — see `--list-devices` |

---

## Offline / no-API mode

```bash
pip install faster-whisper
```

Set in `.env`:
```
STT_BACKEND=local
```

STT now runs fully locally (no internet). The LLM still uses Groq's API — there is no free locally-runnable model at `llama-3.3-70b-versatile` quality, but `faster-whisper` makes transcription free and offline.

---

## Running tests

```bash
pip install pytest
pytest tests/ -v
```

Tests use mocked APIs — **no microphone, no API key required**:

```
tests/test_audio.py       — VAD logic, energy fallback, WAV encoding (10 tests)
tests/test_transcribe.py  — STT dispatch, Groq/local selection, macro resolution (6 tests)
```

If your system `pytest` has a broken third-party plugin at startup:
```bash
python -m pytest tests/ -v -p no:langsmith
```

---

## Cost

**$0.** Groq's free tier provides:
- **7,200 minutes/day** of Whisper audio transcription
- **500,000 tokens/minute** on `llama-3.3-70b-versatile`
- **14,400 API requests/day**

A typical 15-turn demo session uses ~4 minutes of audio and ~6,000 tokens — well under 0.1% of the daily free allowance.

---

## Project structure

```
voice-terminal-agent/
├── voice_agent/
│   ├── __main__.py        # Enables `python -m voice_agent`
│   ├── main.py            # CLI definition and session loop (continuous + ptt)
│   ├── config.py          # .env loader, Config dataclass
│   ├── audio/
│   │   ├── capture.py     # Microphone recording + VAD auto-stop loop
│   │   ├── vad.py         # webrtcvad wrapper with energy-threshold fallback
│   │   └── transcribe.py  # STT dispatcher — Groq Whisper or faster-whisper
│   ├── agent/
│   │   ├── groq_agent.py  # Groq-backed coding agent (streaming, history, slash cmds)
│   │   └── commands.py    # Voice macro → slash command resolver
│   └── ui/
│       └── display.py     # Rich terminal UI — waveform, panels, streaming output
├── tests/
│   ├── test_audio.py      # Unit tests: VAD, frame size, WAV encoding
│   └── test_transcribe.py # Unit tests: STT dispatch, macro resolution
├── .env.example           # Environment variable template
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

**`webrtcvad-wheels` build fails**  
→ The system falls back to energy-based VAD automatically. No action needed.

**Groq API key error at startup**  
→ Ensure `.env` exists (not just `.env.example`) and contains a valid `GROQ_API_KEY=gsk_...`

**Wrong microphone selected**  
→ `python -m voice_agent --list-devices` then set `DEVICE_INDEX=<number>` in `.env`

**VAD triggers on background noise**  
→ Increase `VAD_AGGRESSIVENESS=3` in `.env`, or use `--mode ptt`

---

## License

MIT — see [LICENSE](LICENSE).
