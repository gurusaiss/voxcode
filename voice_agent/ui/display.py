"""Terminal UI — Rich rendering for the voice input layer.

aider owns its own terminal output (responses, diffs, edits).
This module handles only the voice-interface layer:

  ┌─ VOICE INTERFACE FOR AIDER ───────────────────────────────────┐
  │  model: groq/llama-3.3-70b-versatile  |  mode: continuous     │
  └───────────────────────────────────────────────────────────────┘

  * REC   ########................................   342 rms   <- listening
  * HEARD ##########################..............  1847 rms   <- speech detected

  ┌─ You  (turn 3) ───────────────────────────────────────────────┐
  │  Add error handling so balance can't go negative              │
  └───────────────────────────────────────────────────────────────┘
    ↳ aider                                        <- aider takes over output
"""

import sys
import threading
import time
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.text import Text


# ── waveform constants ────────────────────────────────────────────────────────

BAR_WIDTH  = 40
MAX_RMS    = 600.0   # tuned for typical laptop/USB mic levels
FILL_CHAR  = "#"
EMPTY_CHAR = "."

# ANSI escape codes (work in Windows Terminal, VS Code, PowerShell 7+)
_RESET  = "\033[0m"
_BOLD   = "\033[1m"
_DIM    = "\033[2m"
_RED    = "\033[31m"
_GREEN  = "\033[32m"
_BRED   = "\033[1;31m"
_BGREEN = "\033[1;32m"
_CLR    = "\r\033[K"   # carriage-return + erase-to-end-of-line


def _rms_bar(rms: float) -> str:
    ratio  = min(rms / MAX_RMS, 1.0)
    filled = int(ratio * BAR_WIDTH)
    return FILL_CHAR * filled + EMPTY_CHAR * (BAR_WIDTH - filled)


def _enable_ansi_windows() -> None:
    """Enable VT100 ANSI processing on Windows (no-op on other platforms)."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        k32 = ctypes.windll.kernel32
        # ENABLE_PROCESSED_OUTPUT | ENABLE_WRAP_AT_EOL_OUTPUT | ENABLE_VIRTUAL_TERMINAL_PROCESSING
        k32.SetConsoleMode(k32.GetStdHandle(-11), 7)
    except Exception:
        pass


# ── main UI class ─────────────────────────────────────────────────────────────


class AgentUI:
    def __init__(self, console: Console, model: str, mode: str):
        self.console = console
        self.model   = model
        self.mode    = mode
        self._turn   = 0

        # waveform state — written from recording thread, read from waveform thread
        self._live_rms: float       = 0.0
        self._speech_detected: bool = False
        self._waveform_active       = threading.Event()
        self._waveform_thread: Optional[threading.Thread] = None

    # ── session lifecycle ─────────────────────────────────────────────────────

    def print_banner(self) -> None:
        self.console.print()
        self.console.print(
            Panel(
                Text.assemble(
                    ("  VOICE INTERFACE FOR AIDER", "bold cyan"),
                    ("  |  voice-driven input layer  |  Groq STT", "dim"),
                ),
                subtitle=f"[dim]model: {self.model}  |  mode: {self.mode}[/dim]",
                border_style="cyan",
                padding=(0, 2),
            )
        )

    def print_help(self, macro_text: str) -> None:
        self.console.print(
            Panel(
                f"[bold]Keyboard shortcuts[/bold]\n"
                f"  [cyan]Ctrl+C[/cyan]  - exit session\n\n"
                f"[bold]Voice macros[/bold]  (aider commands spoken naturally)\n{macro_text}",
                title="[bold]Help[/bold]",
                border_style="dim",
            )
        )

    def print_ready(self) -> None:
        self.console.print(
            "\n[bold green]*[/bold green] [green]Listening...[/green]  "
            "[dim](speak naturally — pause to send to aider)[/dim]\n"
        )

    def print_waiting_ptt(self) -> None:
        self.console.print(
            "\n[bold yellow]*[/bold yellow] [yellow]Hold SPACE to record[/yellow]\n"
        )

    # ── waveform ──────────────────────────────────────────────────────────────

    def update_rms(self, rms: float) -> None:
        """Called every 30 ms from the recording thread."""
        self._live_rms = rms

    def notify_speech_start(self) -> None:
        """Called the first moment VAD detects speech."""
        self._speech_detected = True

    def start_waveform(self) -> None:
        self._live_rms        = 0.0
        self._speech_detected = False
        self._waveform_active.set()
        self._waveform_thread = threading.Thread(
            target=self._waveform_loop, daemon=True
        )
        self._waveform_thread.start()

    def stop_waveform(self) -> None:
        self._waveform_active.clear()
        if self._waveform_thread:
            self._waveform_thread.join(timeout=0.6)

    def _waveform_loop(self) -> None:
        """Renders the live audio bar in-place using raw ANSI escape codes.

        Runs in its own daemon thread.  Uses sys.stdout directly (bypassing
        Rich) so that \\r actually moves the cursor to column 0 instead of
        printing a new line — which is what Rich's console.print() does.
        """
        _enable_ansi_windows()
        sys.stdout.write("\n")
        sys.stdout.flush()

        try:
            while self._waveform_active.is_set():
                bar = _rms_bar(self._live_rms)
                rms = int(self._live_rms)

                if self._speech_detected:
                    prefix    = f"{_BGREEN}* HEARD{_RESET}"
                    bar_color = _GREEN
                else:
                    prefix    = f"{_BRED}* REC  {_RESET}"
                    bar_color = _RED

                line = (
                    f"{_CLR}"
                    f"{prefix}  "
                    f"{bar_color}{bar}{_RESET}  "
                    f"{_DIM}{rms:5d} rms{_RESET}"
                )
                sys.stdout.write(line)
                sys.stdout.flush()
                time.sleep(0.04)   # ~25 fps

        finally:
            sys.stdout.write(f"{_CLR}\n")
            sys.stdout.flush()

    # ── content panels ────────────────────────────────────────────────────────

    def print_transcription(self, text: str) -> None:
        self._turn += 1
        self.console.print(
            Panel(
                f"[bold]{text}[/bold]",
                title=f"[cyan]You  [dim](turn {self._turn})[/dim][/cyan]",
                border_style="cyan",
                padding=(0, 2),
            )
        )

    # ── status spinners ───────────────────────────────────────────────────────

    def status_transcribing(self):
        return self.console.status(
            "[yellow]Transcribing speech...[/yellow]", spinner="dots"
        )

    # ── errors & info ─────────────────────────────────────────────────────────

    def print_error(self, message: str) -> None:
        self.console.print(
            Panel(
                f"[red]{message}[/red]",
                title="[red]Error[/red]",
                border_style="red",
                padding=(0, 2),
            )
        )

    def print_empty_transcription(self) -> None:
        self.console.print(
            "[dim]  (no speech detected — listening again)[/dim]\n"
        )

    def print_exit(self) -> None:
        self.console.print(
            Panel(
                f"[dim]Session ended after [bold]{self._turn}[/bold] turn(s).[/dim]",
                border_style="dim",
            )
        )
