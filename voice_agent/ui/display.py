"""Terminal UI - all rich rendering lives here.

Layout during a session:
  ┌─ VOICE CODING AGENT ─────────────────────────────────────────────────┐
  |  Model: llama-3.3-70b-versatile  |  Turn: 4  |  Mode: continuous    |
  └──────────────────────────────────────────────────────────────────────┘
  ┌─ Waveform ──────────────────────────────────────────────────────────┐
  |  ▁▂▄▇█▇▄▂▁░░░░░░░░░  Recording...                                  |
  └────────────────────────────────────────────────────────────────────-┘
  ┌─ You said ──────────────────────────────────────────────────────────┐
  |  "Create a Python class for a bank account"                         |
  └────────────────────────────────────────────────────────────────────-┘
  ┌─ Agent ─────────────────────────────────────────────────────────────┐
  |  Here's a `BankAccount` class:                                      |
  |  ```python                                                          |
  |  class BankAccount: ...                                             |
  |  ```                                                                |
  └─────────────────────────────────────────────────────────────────────┘
"""

import math
import threading
import time
from typing import Optional

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.rule import Rule
from rich.text import Text
from rich import print as rprint


# ── constants ─────────────────────────────────────────────────────────────────

BAR_WIDTH = 32
MAX_RMS = 3000.0
_FILL_CHAR = "#"
_EMPTY_CHAR = "."


# ── helpers ───────────────────────────────────────────────────────────────────


def _rms_to_bar(rms: float) -> str:
    ratio = min(rms / MAX_RMS, 1.0)
    filled = max(1, int(ratio * BAR_WIDTH))
    return _FILL_CHAR * filled + _EMPTY_CHAR * (BAR_WIDTH - filled)


# ── UI class ──────────────────────────────────────────────────────────────────


class AgentUI:
    def __init__(self, console: Console, model: str, mode: str):
        self.console = console
        self.model = model
        self.mode = mode
        self._turn = 0
        self._live_rms: float = 0.0
        self._waveform_thread: Optional[threading.Thread] = None
        self._waveform_active = threading.Event()

    # ── session lifecycle ──────────────────────────────────────────────────────

    def print_banner(self) -> None:
        self.console.print()
        self.console.print(
            Panel(
                Text.assemble(
                    ("  VOICE CODING AGENT", "bold cyan"),
                    ("  |  voice-driven terminal AI  |  Groq-powered", "dim"),
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
                f"  [cyan]ENTER[/cyan]   - start a new recording turn (continuous mode)\n"
                f"  [cyan]SPACE[/cyan]   - hold to record, release to send (ptt mode)\n"
                f"  [cyan]Ctrl+C[/cyan]  - exit session\n\n"
                f"[bold]Voice macros[/bold]\n{macro_text}",
                title="[bold]Help[/bold]",
                border_style="dim",
            )
        )

    def print_ready(self) -> None:
        self.console.print(
            "\n[bold green]*[/bold green] [green]Listening...[/green]  "
            "[dim](speak at any time - pause to send)[/dim]\n"
        )

    def print_waiting_ptt(self) -> None:
        self.console.print(
            "\n[bold yellow]*[/bold yellow] [yellow]Hold SPACE to record[/yellow]\n"
        )

    # ── waveform live display ─────────────────────────────────────────────────

    def start_waveform(self) -> None:
        self._waveform_active.set()
        self._waveform_thread = threading.Thread(
            target=self._waveform_loop, daemon=True
        )
        self._waveform_thread.start()

    def stop_waveform(self) -> None:
        self._waveform_active.clear()
        if self._waveform_thread:
            self._waveform_thread.join(timeout=0.5)
        self.console.print()   # newline after waveform

    def update_rms(self, rms: float) -> None:
        self._live_rms = rms

    def _waveform_loop(self) -> None:
        while self._waveform_active.is_set():
            bar = _rms_to_bar(self._live_rms)
            self.console.print(
                f"\r[bold red]* REC[/bold red]  [red]{bar}[/red]  [dim]{self._live_rms:5.0f} rms[/dim]",
                end="",
                highlight=False,
            )
            time.sleep(0.04)

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

    def print_macro_result(self, result: str) -> None:
        self.console.print(
            Panel(
                f"[dim]{result}[/dim]",
                title="[yellow]Command[/yellow]",
                border_style="yellow",
                padding=(0, 2),
            )
        )

    def start_response(self) -> None:
        self.console.print(Rule("[bold green]Agent[/bold green]", style="green"))

    def end_response(self) -> None:
        self.console.print(Rule(style="dim"))

    def print_response_chunk(self, chunk: str) -> None:
        self.console.print(chunk, end="", highlight=False)

    def print_response_markdown(self, text: str) -> None:
        self.console.print(Markdown(text))

    # ── status spinners ───────────────────────────────────────────────────────

    def status_transcribing(self):
        return self.console.status("[yellow]Transcribing...[/yellow]", spinner="dots")

    def status_thinking(self):
        return self.console.status("[green]Thinking...[/green]", spinner="dots2")

    # ── errors ────────────────────────────────────────────────────────────────

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
        self.console.print("[dim]  (no speech detected - listening again)[/dim]\n")

    def print_exit(self) -> None:
        self.console.print(
            Panel(
                f"[dim]Session ended after [bold]{self._turn}[/bold] turns.[/dim]",
                border_style="dim",
            )
        )
