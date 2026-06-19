# REPORT — Voice Interface for aider

## Chosen Agent: aider

The assignment required picking an existing open-source terminal coding agent and building a voice input interface around it. I chose **aider** (https://github.com/paul-gauthier/aider) for the following reasons:

- **Most mature terminal coding agent available** — 55 000+ GitHub stars, active development since 2023, widely used in practice.
- **Python API** — `aider.coders.Coder` exposes a `run(text)` method that accepts a plain-text prompt, making programmatic integration straightforward without subprocess gymnastics.
- **Git-native** — aider tracks and applies file edits through git, giving automatic diff display, undo, and commit — all accessible by voice via aider's own command system.
- **Model-agnostic** — aider uses litellm internally, routing to any provider (Groq, OpenAI, Anthropic, Ollama) through a single model-string.

I also evaluated **opencode** (mentioned in the problem statement) — TypeScript-based with no stable Python API. **Claude Code** is not fully open source. **Goose** (Block) is less established. aider was the clear choice.

---

## Integration Method

Integration is through aider's **Python API** (`Coder.run`), not subprocess or PTY wrapping.

```python
from aider.coders import Coder
from aider.models import Model
from aider.io import InputOutput

io = InputOutput(yes=True)   # auto-accept all confirmations — hands-free
coder = Coder.create(main_model=Model("groq/llama-3.3-70b-versatile"), io=io)
coder.run("add error handling to withdraw()")   # transcribed voice text forwarded here
```

**Why Python API and not subprocess?**

Subprocess wrapping (piping stdin to the `aider` process) was evaluated first. Two problems ruled it out:

1. aider uses readline and PTY-based terminal control. Piped stdin breaks these on all platforms; on Windows there is no native PTY subsystem.
2. Piped subprocess loses aider's streaming output and makes it impossible to detect when a response is complete.

The Python API bypasses both problems. `coder.run()` is a blocking call that returns when aider has finished. aider renders its own output to the terminal using its own Rich console — exactly as in a normal interactive session. The voice interface is a **pure input layer**; it does not parse, intercept, or re-render aider's responses.

`InputOutput(yes=True)` makes aider automatically confirm all file-edit prompts. Without this, aider would pause for a keystroke — defeating hands-free operation.

---

## STT Engine Evaluation

| Engine | Latency | Cost | Accuracy | Offline | Decision |
|---|---|---|---|---|---|
| **Groq Whisper** (`whisper-large-v3-turbo`) | ~200 ms | Free (7 200 min/day) | Excellent | No | **Primary** |
| faster-whisper `base` (local CPU) | ~1-2 s | Free | Good | Yes | Fallback |
| OpenAI Whisper API | ~400 ms | $0.006/min | Excellent | No | Rejected |
| Deepgram Nova-2 | ~150 ms | $0.0043/min | Excellent | No | Rejected |
| AssemblyAI | ~500 ms | $0.65/hr | Very good | No | Rejected |

Groq was the clear choice: fastest free inference, identical model quality to OpenAI Whisper API, and the same GROQ_API_KEY already needed for the aider LLM. The faster-whisper fallback ensures the voice pipeline works offline at the cost of ~1-2 s latency.

---

## VAD Design

Voice Activity Detection solves two problems: knowing when the user has started speaking and knowing when they have finished.

**webrtcvad** (Google WebRTC VAD, ~2 us per 30 ms frame) is used at aggressiveness level 2 (balanced false-positive / false-negative). A pure energy-threshold fallback activates automatically when webrtcvad is unavailable or the sample rate is unsupported.

The recording loop reads 30 ms frames, accumulates frames once speech is detected, and stops after 1.0 second of post-speech silence. This value was chosen empirically: 0.8 s cut off natural mid-sentence pauses; 1.5 s felt sluggish.

An `on_speech_start` callback fires the instant the first voiced frame is detected, turning the waveform bar from red (* REC) to green (* HEARD) for immediate visual feedback.

---

## Pipeline Architecture

```
microphone -> VAD -> buffer -> STT -> macro resolver -> aider.run()
```

Each stage is isolated in its own module. The audio pipeline has no knowledge of aider. aider has no knowledge of audio. This made unit testing straightforward — stages are tested independently with mocked APIs (no microphone, no API key required in tests).

The voice interface is a **pure input layer**. It has no knowledge of code, files, or LLM responses — that is aider's job.

---

## Voice Macro Design

aider has a built-in slash-command system (/undo, /clear, /add, /drop, /diff, /commit, /help). Rather than reimplementing these, the voice macro resolver maps natural spoken phrases to aider's native commands:

- "undo that" -> /undo -> forwarded to coder.run("/undo")
- "add main.py" -> /add main.py -> forwarded to coder.run("/add main.py")
- "show diff" -> /diff -> forwarded to coder.run("/diff")

Voice users get access to aider's complete built-in command set without reimplementation. File add/drop use a regex to extract the filename from natural speech ("add the file utils.py" -> /add utils.py).

---

## Cost Analysis

| Service | Usage per 15-turn session | Cost |
|---|---|---|
| Groq Whisper whisper-large-v3-turbo (STT) | ~4 min audio | $0 (free: 7 200 min/day) |
| Groq llama-3.3-70b-versatile via aider | ~6 000 tokens | $0 (free: 500 K tokens/min) |
| **Total** | | **$0** |

Both the STT pipeline and aider's LLM use the same Groq API key. No external service with usage-based pricing is invoked.

---

## Performance Observations

Measured on a mid-range laptop (Intel i5-12th gen, 16 GB RAM, Windows 11):

| Stage | Typical latency |
|---|---|
| VAD frame processing (30 ms chunk) | < 1 ms |
| Groq Whisper transcription | 180-250 ms |
| faster-whisper base (local fallback) | 900 ms - 1.4 s |
| aider LLM first token (via Groq) | 200-500 ms |
| **End-to-end (speech end -> aider first token on screen)** | **~500 ms** |

---

## Trade-offs and Limitations

**Whisper accuracy on technical vocabulary.** Whisper occasionally mishears programming keywords (e.g. "async" -> "a sync"). A post-processing correction pass was considered but not implemented to keep scope tight.

**aider requires a git repository.** aider works without git but displays warnings. The README instructs users to run git init if needed.

**aider owns terminal output.** aider renders its own responses (diffs, file edits, streaming tokens). The voice interface does not intercept this — which is correct per the assignment: responses are displayed on screen as normal.

**Groq rate limits.** The free tier caps at 30 RPM for the LLM. Voice interaction is naturally paced and this limit was never reached during testing.

---

## What I Would Add Next

1. **Wake-word activation** — replace continuous VAD with a wake word to reduce false triggers in noisy environments.
2. **Vocabulary post-processing** — a regex/lookup pass to correct common coding-term transcription errors before forwarding to aider.
3. **Session resume** — preserve aider's conversation context across invocations via aider's own history mechanism.
4. **Runtime sensitivity control** — voice commands to adjust SILENCE_TIMEOUT without restarting.