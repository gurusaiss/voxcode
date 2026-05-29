"""Voice macro resolution — maps natural-language phrases to agent slash commands.

Standard macros are matched exactly (case-insensitive, trailing punctuation ignored).
Save-with-filename is matched by regex: "save as main.py", "save that as utils.py".
"""

import re

# ── exact macros ──────────────────────────────────────────────────────────────

MACROS: dict[str, str] = {
    # Session control
    "exit": "/exit",
    "quit": "/exit",
    "exit session": "/exit",
    "quit session": "/exit",
    "goodbye": "/exit",
    "bye": "/exit",

    # History
    "undo": "/undo",
    "undo that": "/undo",
    "revert": "/undo",
    "revert that": "/undo",
    "go back": "/undo",

    # Context
    "clear": "/clear",
    "clear history": "/clear",
    "reset": "/clear",
    "start over": "/clear",
    "new session": "/clear",

    # File management
    "show files": "/files",
    "list files": "/files",
    "what files": "/files",
    "current files": "/files",

    # Directory listing
    "list directory": "/ls",
    "show directory": "/ls",
    "what's here": "/ls",
    "what is here": "/ls",

    # Save code to disk (no filename → auto-named)
    "save": "/save",
    "save that": "/save",
    "save the code": "/save",
    "save to file": "/save",
    "write to file": "/save",
    "write that": "/save",
    "write the code": "/save",

    # Run last saved file
    "run": "/run",
    "run that": "/run",
    "run the code": "/run",
    "execute": "/run",
    "execute that": "/run",
    "run the file": "/run",

    # Help
    "help": "/help",
    "commands": "/help",
    "what can you do": "/help",
    "show commands": "/help",
    "show macros": "/help",

    # History review
    "show history": "/history",
    "conversation history": "/history",
    "history": "/history",
}

# ── save-with-filename regex ──────────────────────────────────────────────────
# Matches: "save as main.py", "save that as utils.py", "save to solution.py"

_SAVE_AS = re.compile(
    r"^save(?:\s+that)?\s+(?:as|to)\s+([\w\-]+(?:\.\w+)?)[.!?]?\s*$",
    re.IGNORECASE,
)

# ── exact-macro compiled pattern ──────────────────────────────────────────────

_PATTERN = re.compile(
    r"^\s*(" + "|".join(re.escape(k) for k in sorted(MACROS, key=len, reverse=True)) + r")\s*[.!?]?\s*$",
    re.IGNORECASE,
)


# ── public API ────────────────────────────────────────────────────────────────


def resolve(text: str) -> str:
    """Return the slash command if text is a known macro, otherwise return text unchanged.

    Handles:
      - Exact macros (case-insensitive, trailing punctuation stripped)
      - "save as <filename>" with optional extension inference
    """
    stripped = text.strip()

    # 1. Save-with-filename: "save as main.py" → /save main.py
    m = _SAVE_AS.match(stripped)
    if m:
        fname = m.group(1)
        if "." not in fname:
            fname += ".py"   # default to .py if no extension given
        return f"/save {fname}"

    # 2. Standard exact macro
    m = _PATTERN.match(stripped)
    if m:
        return MACROS[m.group(1).lower().strip()]

    return text


def is_exit(text: str) -> bool:
    return resolve(text) == "/exit"


def describe_macros() -> str:
    """Return a human-readable list of available voice macros for the help panel."""
    seen: dict[str, list[str]] = {}
    for phrase, cmd in MACROS.items():
        seen.setdefault(cmd, []).append(f'"{phrase}"')

    lines = []
    order = ["/exit", "/undo", "/clear", "/save", "/run", "/ls", "/files", "/history", "/help"]
    for cmd in order:
        if cmd in seen:
            phrases = seen[cmd][:3]
            lines.append(f"  {cmd:20s} -> {', '.join(phrases)}")
    return "\n".join(lines)
