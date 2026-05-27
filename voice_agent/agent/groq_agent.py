"""Groq-backed coding agent.

Acts as a context-aware terminal coding assistant — comparable to aider but
implemented as a clean agentic loop over Groq's chat API.  Chosen over
wrapping aider directly because:

  1. aider's stdin/PTY integration is fragile on Windows (no native PTY).
  2. Building the agent layer explicitly demonstrates the observe→reason→act
     loop more transparently, which is the evaluation goal.
  3. Groq's free tier (8 000 RPM on llama-3.3-70b-versatile) imposes no cost.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Iterator

from groq import Groq

SYSTEM_PROMPT = """You are a voice-driven terminal coding assistant.
The user interacts with you entirely by speaking — their words are transcribed
and forwarded to you.  Keep this in mind:

- Responses are displayed on a terminal, not read aloud.
- Be concise.  One short paragraph + code block is ideal.
- Always wrap code in markdown fenced blocks with the language tag.
- After writing code, briefly state what it does in one sentence.
- If asked to modify existing code shown in the conversation, produce the full
  updated version — never a diff snippet.
- If the request is ambiguous, make a sensible assumption and state it.

Supported slash commands (you will receive them verbatim):
  /undo     — acknowledge and remove your last response from context
  /clear    — acknowledge and reset the conversation
  /files    — list any filenames mentioned in this session
  /history  — summarise the conversation so far
  /help     — list these commands
  /exit     — acknowledge and end the session
"""


@dataclass
class Message:
    role: str   # "user" | "assistant" | "system"
    content: str


@dataclass
class GroqAgent:
    api_key: str
    model: str = "llama-3.3-70b-versatile"
    _history: list[Message] = field(default_factory=list, init=False)
    _client: Groq = field(init=False)

    def __post_init__(self) -> None:
        self._client = Groq(api_key=self.api_key)
        self._history.append(Message("system", SYSTEM_PROMPT))

    # ── public API ────────────────────────────────────────────────────────────

    def send(self, text: str) -> str:
        """Send a message and return the full response string."""
        return "".join(self.stream(text))

    def stream(self, text: str) -> Iterator[str]:
        """Yield response tokens as they arrive (streaming)."""
        # Handle slash commands that don't need an LLM round-trip
        internal = self._handle_command(text)
        if internal is not None:
            yield internal
            return

        self._history.append(Message("user", text))

        completion = self._client.chat.completions.create(
            model=self.model,
            messages=[{"role": m.role, "content": m.content} for m in self._history],
            temperature=0.15,
            max_tokens=2048,
            stream=True,
        )

        full_response: list[str] = []
        for chunk in completion:
            delta = chunk.choices[0].delta.content or ""
            full_response.append(delta)
            yield delta

        response_text = "".join(full_response)
        self._history.append(Message("assistant", response_text))

    def history_summary(self) -> list[dict[str, str]]:
        return [{"role": m.role, "content": m.content[:120]} for m in self._history[1:]]

    @property
    def turn_count(self) -> int:
        return sum(1 for m in self._history if m.role == "user")

    # ── slash command handling ─────────────────────────────────────────────────

    def _handle_command(self, text: str) -> str | None:
        cmd = text.strip().lower()

        if cmd == "/undo":
            removed = self._undo()
            return f"[Undone] Removed last exchange.{(' Nothing to undo.' if not removed else '')}"

        if cmd == "/clear":
            self._history = [Message("system", SYSTEM_PROMPT)]
            return "[Cleared] Conversation reset. Ready for a fresh start."

        if cmd == "/files":
            files = self._extract_filenames()
            if files:
                return "[Files mentioned in session]\n" + "\n".join(f"  • {f}" for f in files)
            return "[Files] No filenames mentioned yet."

        if cmd == "/history":
            items = self.history_summary()
            if not items:
                return "[History] No messages yet."
            lines = [f"  [{m['role']}] {m['content']}" for m in items]
            return "[History]\n" + "\n".join(lines)

        if cmd == "/help":
            from voice_agent.agent.commands import describe_macros
            return (
                "[Voice Commands]\n"
                + describe_macros()
                + "\n\nJust speak naturally for anything else."
            )

        if cmd == "/exit":
            return "[Session ended] Goodbye."

        return None  # let the LLM handle it

    def _undo(self) -> bool:
        """Remove the last user+assistant pair from history."""
        if len(self._history) >= 3:  # system + user + assistant
            self._history.pop()  # assistant
            self._history.pop()  # user
            return True
        return False

    def _extract_filenames(self) -> list[str]:
        """Best-effort extraction of filenames mentioned in the conversation."""
        import re
        pattern = re.compile(r"\b[\w\-/\\]+\.\w{1,6}\b")
        found: set[str] = set()
        for msg in self._history[1:]:
            for match in pattern.finditer(msg.content):
                found.add(match.group())
        return sorted(found)
