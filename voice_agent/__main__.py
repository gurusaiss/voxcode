import sys
import io

# Ensure UTF-8 output on Windows (Windows Terminal supports it; legacy cmd may not)
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from voice_agent.main import cli

if __name__ == "__main__":
    cli()
