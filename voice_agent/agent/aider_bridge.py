"""Thin bridge from the voice pipeline to aider's Python API.

aider (https://github.com/paul-gauthier/aider) is an open-source terminal
coding agent that edits source files in a local git repo through conversation.
This module drives it programmatically — transcribed speech arrives as plain
text and is forwarded to aider's Coder, which handles all LLM interaction,
code editing, and terminal output itself.

The voice interface is purely an input layer: capture → transcribe → run().
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class AiderBridge:
    """Wraps aider's Coder to accept text input from the voice pipeline."""

    groq_api_key: str
    model: str = "groq/llama-3.3-70b-versatile"
    _coder: object = field(default=None, init=False)
    _turn_count: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        # aider's litellm reads GROQ_API_KEY automatically for groq/* models
        os.environ.setdefault("GROQ_API_KEY", self.groq_api_key)

        from aider.coders import Coder
        from aider.models import Model
        from aider.io import InputOutput

        io = InputOutput(yes=True)   # auto-accept all confirmations — hands-free
        model = Model(self.model)

        self._coder = Coder.create(
            main_model=model,
            io=io,
            auto_commits=False,     # don't commit on every edit — user controls git
        )

    def run(self, text: str) -> None:
        """Forward text to aider. Aider handles LLM interaction and terminal output."""
        self._coder.run(text)
        self._turn_count += 1

    @property
    def turn_count(self) -> int:
        return self._turn_count
