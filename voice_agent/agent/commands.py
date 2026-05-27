"""Voice macro resolution — maps natural-language phrases to agent slash commands."""

import re

# Maps normalised spoken phrase → agent command
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

    # Help
    "help": "/help",
    "commands": "/help",
    "what can you do": "/help",
    "show commands": "/help",

    # History review
    "show history": "/history",
    "conversation history": "/history",
}

# Compiled pattern for faster matching
_PATTERN = re.compile(
    r"^\s*(" + "|".join(re.escape(k) for k in sorted(MACROS, key=len, reverse=True)) + r")\s*[.!?]?\s*$",
    re.IGNORECASE,
)


def resolve(text: str) -> str:
    """Return the slash command if text is a known macro, otherwise return text unchanged."""
    m = _PATTERN.match(text)
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
    for cmd, phrases in sorted(seen.items()):
        lines.append(f"  {cmd:20s} -> {', '.join(phrases[:3])}")
    return "\n".join(lines)
