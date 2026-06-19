"""Voice macro resolution — maps natural-language phrases to aider slash commands.

aider has its own built-in command system (/undo, /clear, /add, /drop, etc.).
Standard macros are matched exactly (case-insensitive, trailing punctuation ignored).
File-add and file-drop are matched by regex to extract the filename.
"""

import re

# ── exact macros ──────────────────────────────────────────────────────────────
# All mapped values are aider native commands — passed directly to coder.run().
# The sole exception is /exit which is handled by the voice loop itself.

MACROS: dict[str, str] = {
    # Session exit (handled before reaching aider)
    "exit": "/exit",
    "quit": "/exit",
    "exit session": "/exit",
    "quit session": "/exit",
    "goodbye": "/exit",
    "bye": "/exit",

    # Undo last aider edit
    "undo": "/undo",
    "undo that": "/undo",
    "undo last change": "/undo",
    "revert": "/undo",
    "revert that": "/undo",

    # Clear conversation context
    "clear": "/clear",
    "clear history": "/clear",
    "start over": "/clear",
    "new session": "/clear",
    "reset": "/clear",

    # List files in aider's context
    "list files": "/ls",
    "show files": "/ls",
    "what files": "/ls",
    "files in context": "/ls",
    "what's in context": "/ls",

    # Show diff of uncommitted changes
    "show diff": "/diff",
    "what changed": "/diff",
    "show changes": "/diff",
    "diff": "/diff",

    # Commit current changes to git
    "commit": "/commit",
    "commit changes": "/commit",
    "save changes": "/commit",

    # Run a shell command (passed through to aider's /run handler)
    "run tests": "/run pytest",
    "run the tests": "/run pytest",

    # Help
    "help": "/help",
    "show commands": "/help",
    "what can you do": "/help",
    "show help": "/help",
}

# ── file add/drop regex ───────────────────────────────────────────────────────
# "add main.py"           → /add main.py
# "add the file utils.py" → /add utils.py
# "add file src/main.py"  → /add src/main.py

_ADD_FILE = re.compile(
    r"^add(?:\s+(?:the\s+)?file)?\s+([\w\-./\\]+\.\w+)[.!?]?\s*$",
    re.IGNORECASE,
)

# "drop main.py"            → /drop main.py
# "remove the file utils.py" → /drop utils.py

_DROP_FILE = re.compile(
    r"^(?:drop|remove)(?:\s+(?:the\s+)?file)?\s+([\w\-./\\]+\.\w+)[.!?]?\s*$",
    re.IGNORECASE,
)

# ── exact-macro compiled pattern ──────────────────────────────────────────────

_PATTERN = re.compile(
    r"^\s*(" + "|".join(re.escape(k) for k in sorted(MACROS, key=len, reverse=True)) + r")\s*[.!?]?\s*$",
    re.IGNORECASE,
)


# ── public API ────────────────────────────────────────────────────────────────


def resolve(text: str) -> str:
    """Return the aider slash command if text is a known macro, else text unchanged.

    Handles:
      - "add main.py"  → /add main.py   (aider adds file to context)
      - "drop main.py" → /drop main.py  (aider removes file from context)
      - Exact macros (case-insensitive, trailing punctuation stripped)
      - Everything else passes through unchanged to aider as a coding request
    """
    stripped = text.strip()

    m = _ADD_FILE.match(stripped)
    if m:
        return f"/add {m.group(1)}"

    m = _DROP_FILE.match(stripped)
    if m:
        return f"/drop {m.group(1)}"

    m = _PATTERN.match(stripped)
    if m:
        return MACROS[m.group(1).lower().strip()]

    return text


def is_exit(text: str) -> bool:
    return resolve(text) == "/exit"


def describe_macros() -> str:
    """Return a human-readable list of voice macros for the help panel."""
    seen: dict[str, list[str]] = {}
    for phrase, cmd in MACROS.items():
        seen.setdefault(cmd, []).append(f'"{phrase}"')

    lines = []
    order = ["/exit", "/undo", "/clear", "/ls", "/diff", "/commit", "/help"]
    for cmd in order:
        if cmd in seen:
            phrases = seen[cmd][:2]
            lines.append(f"  {cmd:22s} -> {', '.join(phrases)}")
    lines.append('  /add <file>            -> "add main.py", "add file utils.py"')
    lines.append('  /drop <file>           -> "drop main.py", "remove utils.py"')
    return "\n".join(lines)
