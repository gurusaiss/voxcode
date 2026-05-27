"""Entry point — CLI definition and main session loop."""

from __future__ import annotations

import sys

import click
from rich.console import Console

from voice_agent.config import load_config, Config
from voice_agent.audio.capture import record_continuous, record_push_to_talk, list_devices
from voice_agent.audio.transcribe import transcribe
from voice_agent.agent.groq_agent import GroqAgent
from voice_agent.agent.commands import resolve, is_exit, describe_macros
from voice_agent.ui.display import AgentUI


# ── CLI ───────────────────────────────────────────────────────────────────────


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.option(
    "--mode",
    type=click.Choice(["continuous", "ptt"]),
    default=None,
    help="continuous = VAD auto-detect (default) | ptt = hold SPACE to record",
)
@click.option(
    "--stt",
    type=click.Choice(["groq", "local"]),
    default=None,
    help="STT backend: groq (Groq Whisper API) | local (faster-whisper, offline)",
)
@click.option(
    "--model",
    default=None,
    help="LLM model for the coding agent (default: llama-3.3-70b-versatile)",
)
@click.option("--list-devices", "show_devices", is_flag=True, help="List audio input devices and exit")
@click.option("--help-macros", "show_macros", is_flag=True, help="Show all voice macros and exit")
def cli(
    mode: str | None,
    stt: str | None,
    model: str | None,
    show_devices: bool,
    show_macros: bool,
) -> None:
    """Voice Terminal Agent — hands-free voice interface for a terminal AI coding agent.

    \b
    Quick start:
      1. Copy .env.example to .env and add your GROQ_API_KEY
      2. Run:  python -m voice_agent
      3. Speak.  Pause to send.  Say "exit" to quit.
    """
    console = Console()

    if show_devices:
        console.print("[bold]Available microphone devices:[/bold]")
        console.print(list_devices())
        return

    if show_macros:
        console.print("[bold]Voice macros:[/bold]\n" + describe_macros())
        return

    try:
        cfg = load_config()
    except EnvironmentError as exc:
        console.print(f"[red]Configuration error:[/red] {exc}")
        sys.exit(1)

    # CLI flags override .env settings
    effective_mode  = mode  or cfg.record_mode
    effective_stt   = stt   or cfg.stt_backend
    effective_model = model or cfg.agent_model

    _run_session(console, cfg, effective_mode, effective_stt, effective_model)


# ── session bootstrap ─────────────────────────────────────────────────────────


def _run_session(
    console: Console,
    cfg: Config,
    mode: str,
    stt_backend: str,
    agent_model: str,
) -> None:
    ui    = AgentUI(console, model=agent_model, mode=mode)
    agent = GroqAgent(api_key=cfg.groq_api_key, model=agent_model)

    ui.print_banner()
    ui.print_help(describe_macros())

    stt_label = (
        "Groq Whisper (whisper-large-v3-turbo)"
        if stt_backend == "groq"
        else "faster-whisper local (base model)"
    )
    console.print(f"[dim]STT: {stt_label}[/dim]\n")

    if mode == "continuous":
        _continuous_loop(console, ui, agent, cfg, stt_backend)
    else:
        _ptt_loop(console, ui, agent, cfg, stt_backend)


# ── continuous VAD loop ───────────────────────────────────────────────────────


def _continuous_loop(
    console: Console,
    ui: AgentUI,
    agent: GroqAgent,
    cfg: Config,
    stt_backend: str,
) -> None:
    """Main loop: listen → record (VAD) → transcribe → respond → repeat.

    Pipeline per turn:
      1. Waveform bar shows in red while waiting for speech
      2. Bar turns green the instant speech is detected (on_speech_start)
      3. Recording stops after silence_timeout (default 1.0 s)
      4. "Sending to Groq..." spinner — immediate feedback
      5. Transcription result shown
      6. "Agent thinking..." spinner
      7. Agent response streams token by token
      8. Loop back to step 1
    """
    ui.print_ready()

    try:
        while True:
            # ── 1. Record ────────────────────────────────────────────────────
            ui.start_waveform()
            wav = record_continuous(
                sample_rate        = cfg.sample_rate,
                silence_timeout    = cfg.silence_timeout,
                vad_aggressiveness = cfg.vad_aggressiveness,
                on_energy          = ui.update_rms,
                on_speech_start    = ui.notify_speech_start,   # turns bar green
                device             = cfg.device_index,
            )
            ui.stop_waveform()

            if wav is None:
                ui.print_empty_transcription()
                continue

            # ── 2. Transcribe ────────────────────────────────────────────────
            with ui.status_transcribing():
                try:
                    text = transcribe(
                        wav,
                        backend      = stt_backend,
                        groq_api_key = cfg.groq_api_key,
                    )
                except Exception as exc:
                    ui.print_error(f"Transcription failed: {exc}")
                    continue

            if not text or not text.strip():
                ui.print_empty_transcription()
                continue

            ui.print_transcription(text)

            # ── 3. Resolve voice macros ──────────────────────────────────────
            command = resolve(text)

            # ── 4. Exit check ────────────────────────────────────────────────
            if is_exit(text):
                result = agent.send(command)
                ui.print_macro_result(result)
                break

            # ── 5. Non-LLM slash commands (undo, clear, …) ──────────────────
            if command.startswith("/"):
                result = agent.send(command)
                ui.print_macro_result(result)
                console.print()
                continue

            # ── 6. Stream LLM response ───────────────────────────────────────
            ui.start_response()
            try:
                for chunk in agent.stream(command):
                    ui.print_response_chunk(chunk)
                console.print()          # newline after streamed content
            except Exception as exc:
                ui.print_error(f"Agent error: {exc}")
            finally:
                ui.end_response()

            console.print()

    except KeyboardInterrupt:
        console.print("\n")

    ui.print_exit()


# ── push-to-talk loop ─────────────────────────────────────────────────────────


def _ptt_loop(
    console: Console,
    ui: AgentUI,
    agent: GroqAgent,
    cfg: Config,
    stt_backend: str,
) -> None:
    """Push-to-talk loop: hold SPACE → release → transcribe → respond."""
    ui.print_waiting_ptt()

    try:
        while True:
            console.print("[dim]Hold SPACE to speak...[/dim]")

            ui.start_waveform()
            wav = record_push_to_talk(
                sample_rate = cfg.sample_rate,
                on_energy   = ui.update_rms,
            )
            ui.stop_waveform()

            if wav is None:
                ui.print_error(
                    "pynput is required for push-to-talk mode.\n"
                    "Run:  pip install pynput"
                )
                break

            with ui.status_transcribing():
                try:
                    text = transcribe(wav, backend=stt_backend, groq_api_key=cfg.groq_api_key)
                except Exception as exc:
                    ui.print_error(f"Transcription failed: {exc}")
                    continue

            if not text or not text.strip():
                ui.print_empty_transcription()
                continue

            ui.print_transcription(text)
            command = resolve(text)

            if is_exit(text):
                result = agent.send(command)
                ui.print_macro_result(result)
                break

            if command.startswith("/"):
                result = agent.send(command)
                ui.print_macro_result(result)
                continue

            ui.start_response()
            try:
                for chunk in agent.stream(command):
                    ui.print_response_chunk(chunk)
                console.print()
            except Exception as exc:
                ui.print_error(f"Agent error: {exc}")
            finally:
                ui.end_response()

            console.print()

    except KeyboardInterrupt:
        console.print("\n")

    ui.print_exit()
