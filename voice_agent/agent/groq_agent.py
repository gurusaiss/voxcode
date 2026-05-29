"""Groq-backed coding agent.

Acts as a context-aware terminal coding assistant — comparable to aider but
implemented as a clean agentic loop over Groq's chat API.  Chosen over
wrapping aider directly because:

  1. aider's stdin/PTY integration is fragile on Windows (no native PTY).
  2. Building the agent layer explicitly demonstrates the observe→reason→act
     loop more transparently, which is the evaluation goal.
  3. Groq's free tier (30 RPM on llama-3.3-70b-versatile) imposes no cost
     for typical voice interaction, which is naturally paced well below the limit.

Voice-exclusive commands (not in typical agents):
  /save [filename]  — extract last code block and write to disk
  /run              — execute the last saved Python file in a subprocess
  /ls               — list files in the current working directory
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from typing import Iterator

from groq import Groq

# ── system prompt ─────────────────────────────────────────────────────────────

def _build_system_prompt() -> str:
    cwd = os.getcwd()
    try:
        files = [f for f in os.listdir(cwd) if not f.startswith('.')]
        file_list = ", ".join(files[:20]) or "(empty)"
    except OSError:
        file_list = "(unavailable)"

    return f"""You are a voice-driven terminal coding assistant.
The user interacts with you entirely by speaking — their words are transcribed
and forwarded to you.  Keep this in mind:

Working directory: {cwd}
Files present: {file_list}

- Responses are displayed on a terminal, not read aloud.
- Be concise.  One short paragraph + code block is ideal.
- Always wrap code in markdown fenced blocks with the correct language tag.
- After writing code, briefly state what it does in one sentence.
- If asked to modify existing code shown in the conversation, produce the
  full updated version — never a diff snippet.
- If the request is ambiguous, make a sensible assumption and state it.
- When the user saves or runs code, acknowledge it naturally.

Supported slash commands (you will receive them verbatim):
  /undo     — acknowledge and remove your last response from context
  /clear    — acknowledge and reset the conversation
  /files    — list filenames mentioned in this session
  /ls       — list files in the current working directory
  /save     — code from your last response was saved to disk
  /run      — the saved file was executed; output follows
  /history  — summarise the conversation so far
  /help     — list these commands
  /exit     — acknowledge and end the session
"""


# ── data types ────────────────────────────────────────────────────────────────


@dataclass
class Message:
    role: str       # "user" | "assistant" | "system"
    content: str


@dataclass
class GroqAgent:
    api_key: str
    model: str = "llama-3.3-70b-versatile"
    _history: list[Message]      = field(default_factory=list, init=False)
    _client: Groq                = field(init=False)
    _last_saved_file: str | None = field(default=None,  init=False)

    def __post_init__(self) -> None:
        self._client = Groq(api_key=self.api_key)
        self._history.append(Message("system", _build_system_prompt()))

    # ── public API ────────────────────────────────────────────────────────────

    def send(self, text: str) -> str:
        """Send a message and return the full response string."""
        return "".join(self.stream(text))

    def stream(self, text: str) -> Iterator[str]:
        """Yield response tokens as they arrive (streaming)."""
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

        self._history.append(Message("assistant", "".join(full_response)))

    def history_summary(self) -> list[dict[str, str]]:
        return [{"role": m.role, "content": m.content[:120]} for m in self._history[1:]]

    @property
    def turn_count(self) -> int:
        return sum(1 for m in self._history if m.role == "user")

    # ── slash command handling ────────────────────────────────────────────────

    def _handle_command(self, text: str) -> str | None:
        cmd   = text.strip()
        lower = cmd.lower()

        if lower == "/undo":
            removed = self._undo()
            return "[Undone] Removed last exchange." if removed else "[Undo] Nothing to undo."

        if lower == "/clear":
            self._history = [Message("system", _build_system_prompt())]
            self._last_saved_file = None
            return "[Cleared] Conversation reset. Ready for a fresh start."

        if lower == "/files":
            files = self._extract_filenames()
            if files:
                return "[Files mentioned in session]\n" + "\n".join(f"  - {f}" for f in files)
            return "[Files] No filenames mentioned yet."

        if lower == "/ls":
            return self._list_cwd()

        if lower.startswith("/save"):
            parts = cmd.split(maxsplit=1)
            filename = parts[1].strip() if len(parts) > 1 else None
            return self._save_last_code(filename)

        if lower == "/run":
            return self._run_last_saved()

        if lower == "/history":
            items = self.history_summary()
            if not items:
                return "[History] No messages yet."
            lines = [f"  [{m['role']}] {m['content']}" for m in items]
            return "[History]\n" + "\n".join(lines)

        if lower == "/help":
            from voice_agent.agent.commands import describe_macros
            return "[Voice Commands]\n" + describe_macros() + "\n\nJust speak naturally for anything else."

        if lower == "/exit":
            return "[Session ended] Goodbye."

        return None     # let the LLM handle it

    # ── /save — write last code block to disk ─────────────────────────────────

    def _save_last_code(self, filename: str | None = None) -> str:
        """Extract the last fenced code block from history and write to disk."""
        code, lang = self._last_code_block()
        if code is None:
            return (
                "[Save] No code block found.\n"
                "  Make sure the agent responded with a fenced code block (```...```).\n"
                "  Try asking again: 'write the code again' then say 'save that'."
            )

        if filename is None:
            ext   = _lang_to_ext(lang)
            fname = f"agent_{int(time.time())}{ext}"
        else:
            fname = filename
            if "." not in fname:
                fname += _lang_to_ext(lang)

        try:
            with open(fname, "w", encoding="utf-8") as fh:
                fh.write(code)
            self._last_saved_file = fname
            abs_path = os.path.abspath(fname)
            lines    = len(code.splitlines())
            return (
                f"[Saved] {abs_path}\n"
                f"  {lines} line(s) written."
            )
        except OSError as exc:
            return f"[Save] Failed to write {fname}: {exc}"

    # ── /run — execute last saved file ────────────────────────────────────────

    def _run_last_saved(self) -> str:
        """Run the last file saved with /save in a subprocess."""
        if not self._last_saved_file:
            return "[Run] No file has been saved yet. Say 'save that' first."

        if not os.path.exists(self._last_saved_file):
            return f"[Run] File not found: {self._last_saved_file}"

        try:
            result = subprocess.run(
                [sys.executable, self._last_saved_file],
                capture_output=True,
                text=True,
                timeout=15,
            )
            out  = result.stdout.strip()
            err  = result.stderr.strip()
            code = result.returncode
            abs_path = os.path.abspath(self._last_saved_file)

            lines = [f"[Run] {abs_path}  (exit {code})"]
            if out:
                lines.append(out)
            if err:
                lines.append(f"[stderr]\n{err}")
            if not out and not err:
                lines.append("(no output)")
            return "\n".join(lines)

        except subprocess.TimeoutExpired:
            return f"[Run] Script timed out after 15 seconds."
        except Exception as exc:
            return f"[Run] Execution failed: {exc}"

    # ── /ls — current directory listing ──────────────────────────────────────

    def _list_cwd(self) -> str:
        cwd = os.getcwd()
        try:
            entries = sorted(os.listdir(cwd))
            dirs    = [e for e in entries if os.path.isdir(e) and not e.startswith('.')]
            files   = [e for e in entries if os.path.isfile(e) and not e.startswith('.')]
            lines   = [f"[Directory] {cwd}"]
            for d in dirs:
                lines.append(f"  [dir]  {d}/")
            for f in files:
                size = os.path.getsize(f)
                lines.append(f"  [file] {f}  ({_human_size(size)})")
            return "\n".join(lines) if len(lines) > 1 else f"[Directory] {cwd}  (empty)"
        except OSError as exc:
            return f"[ls] {exc}"

    # ── helpers ───────────────────────────────────────────────────────────────

    def _undo(self) -> bool:
        """Remove the last user+assistant pair from history."""
        if len(self._history) >= 3:
            self._history.pop()   # assistant
            self._history.pop()   # user
            return True
        return False

    def _last_code_block(self) -> tuple[str | None, str]:
        """Return (code, language) of the last fenced block in assistant history.

        Handles all common LLM code block formats:
          ```python\n...```          standard
          ```python # comment\n...``` language + trailing comment
          ```\n...```                 no language tag
          ``` python\n...```         space before language
        """
        # Pattern: optional space, language word, anything until newline, then code
        pattern = re.compile(r"```[ \t]*(\w*)[^\n]*\n(.*?)```", re.DOTALL)

        for msg in reversed(self._history):
            if msg.role == "assistant":
                blocks = pattern.findall(msg.content)
                if blocks:
                    lang, code = blocks[-1]
                    return code.strip(), lang.lower()
        return None, ""

    def _extract_filenames(self) -> list[str]:
        """Best-effort extraction of filenames mentioned in the conversation."""
        pattern = re.compile(r"\b[\w\-/\\]+\.\w{1,6}\b")
        found: set[str] = set()
        for msg in self._history[1:]:
            for match in pattern.finditer(msg.content):
                found.add(match.group())
        return sorted(found)


# ── utilities ─────────────────────────────────────────────────────────────────


def _lang_to_ext(lang: str) -> str:
    return {
        "python": ".py", "py": ".py",
        "javascript": ".js", "js": ".js",
        "typescript": ".ts", "ts": ".ts",
        "bash": ".sh", "shell": ".sh", "sh": ".sh",
        "go": ".go",
        "rust": ".rs",
        "java": ".java",
        "c": ".c", "cpp": ".cpp", "c++": ".cpp",
        "html": ".html", "css": ".css",
        "json": ".json", "yaml": ".yaml", "yml": ".yml",
        "sql": ".sql",
    }.get(lang, ".txt")


def _human_size(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1024 ** 2:
        return f"{n / 1024:.1f} KB"
    return f"{n / 1024 ** 2:.1f} MB"
