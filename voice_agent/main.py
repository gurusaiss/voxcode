"""Entry point — CLI definition and main session loop."""

from __future__ import annotations

import sys

import click
from rich.console import Console

from voice_agent.config import load_config, Config
from voice_agent.audio.capture import record_continuous, record_push_to_talk, list_devices
from voice_agent.audio.transcribe import transcribe
from voice_agent.agent.aider_bridge import AiderBridge
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
    help="aider LLM model (default: groq/llama-3.3-70b-versatile)",
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
    """Voice Terminal Agent — hands-free voice interface for aider.

    \b
    Quick start:
      1. cd into your project directory (git repo recommended)
      2. Copy .env.example to .env and add your GROQ_API_KEY
      3. Run:  python -m voice_agent
      4. Speak.  Pause to send.  Say "exit" to quit.
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
    effective_model = model or cfg.aider_model

    _run_session(console, cfg, effective_mode, effective_stt, effective_model)


# ── session bootstrap ─────────────────────────────────────────────────────────


def _run_session(
    console: Console,
    cfg: Config,
    mode: str,
    stt_backend: str,
    aider_model: str,
) -> None:
    ui = AgentUI(console, model=aider_model, mode=mode)

    console.print("[dim]Starting aider...[/dim]")
    try:
        agent = AiderBridge(groq_api_key=cfg.groq_api_key, model=aider_model)
    except Exception as exc:
        console.print(f"[red]Failed to initialise aider:[/red] {exc}")
        sys.exit(1)

    ui.print_banner()
    ui.print_help(describe_macros())

    stt_label = (
        "Groq Whisper (whisper-large-v3-turbo)"
        if stt_backend == "groq"
        else "faster-whisper local (base model)"
    )
    console.print(f"[dim]STT: {stt_label}[/dim]\n")

    if not _check_microphone(console, cfg.sample_rate, cfg.device_index):
        sys.exit(1)

    if mode == "continuous":
        _continuous_loop(console, ui, agent, cfg, stt_backend)
    else:
        _ptt_loop(console, ui, agent, cfg, stt_backend)


# ── startup mic check ─────────────────────────────────────────────────────────


def _check_microphone(console: Console, sample_rate: int, device: int | None) -> bool:
    """Try to open the mic for one frame.  Print a helpful error and return False on failure."""
    try:
        import sounddevice as sd
        import numpy as np
        with sd.InputStream(samplerate=sample_rate, channels=1,
                            dtype=np.int16, device=device) as s:
            s.read(int(sample_rate * 0.03))
        console.print("[dim]Microphone OK[/dim]\n")
        return True
    except Exception as exc:
        console.print(
            f"[red]Microphone error:[/red] {exc}\n\n"
            f"[yellow]Tips:[/yellow]\n"
            f"  - Run [cyan]python -m voice_agent --list-devices[/cyan] to see available mics\n"
            f"  - Set [cyan]DEVICE_INDEX=<number>[/cyan] in .env to pick a specific device\n"
            f"  - Check your OS mic permissions"
        )
        return False


# ── continuous VAD loop ───────────────────────────────────────────────────────


def _continuous_loop(
    console: Console,
    ui: AgentUI,
    agent: AiderBridge,
    cfg: Config,
    stt_backend: str,
) -> None:
    """Main loop: listen → record (VAD) → transcribe → send to aider → repeat.

    Pipeline per turn:
      1. Waveform bar shows in red while waiting for speech
      2. Bar turns green the instant speech is detected (on_speech_start)
      3. Recording stops after silence_timeout (default 1.0 s)
      4. "Transcribing..." spinner — immediate feedback
      5. Transcription shown in a panel
      6. Text forwarded to aider — aider renders its own response
      7. Loop back to step 1
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
                on_speech_start    = ui.notify_speech_start,
                device             = cfg.device_index,
            )
            ui.stop_waveform()

            if wav is None:
                ui.print_empty_transcription()
                continue

            # ── 2. Transcribe ─────────────────────────────────────────────────
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

            # ── 3. Resolve voice macros ───────────────────────────────────────
            command = resolve(text)

            # ── 4. Exit check ─────────────────────────────────────────────────
            if is_exit(text):
                console.print("[dim]Ending session...[/dim]")
                break

            # ── 5. Forward to aider ───────────────────────────────────────────
            # All commands (/undo, /clear, /add <f>, /diff, …) and plain coding
            # requests are forwarded to aider — it handles LLM calls, file edits,
            # and terminal output entirely on its own.
            console.print("[dim]  ↳ aider[/dim]\n")
            try:
                agent.run(command)
            except Exception as exc:
                ui.print_error(f"Aider error: {exc}")

            console.print()

    except KeyboardInterrupt:
        console.print("\n")

    ui.print_exit()


# ── push-to-talk loop ─────────────────────────────────────────────────────────


def _ptt_loop(
    console: Console,
    ui: AgentUI,
    agent: AiderBridge,
    cfg: Config,
    stt_backend: str,
) -> None:
    """Push-to-talk loop: hold SPACE → release → transcribe → send to aider."""
    ui.print_waiting_ptt()

    try:
        while True:
            console.print("[dim]Hold SPACE to speak...[/dim]")

            ui.start_waveform()
            wav = record_push_to_talk(
                sample_rate = cfg.sample_rate,
                on_energy   = ui.update_rms,
                device      = cfg.device_index,
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
                console.print("[dim]Ending session...[/dim]")
                break

            console.print("[dim]  ↳ aider[/dim]\n")
            try:
                agent.run(command)
            except Exception as exc:
                ui.print_error(f"Aider error: {exc}")

            console.print()

    except KeyboardInterrupt:
        console.print("\n")

    ui.print_exit()
