"""Unit tests for the transcription pipeline (mocked — no API calls made)."""

from unittest.mock import patch
import pytest

from voice_agent.audio.transcribe import transcribe


DUMMY_WAV = b"RIFF\x00\x00\x00\x00WAVEfmt "  # minimal WAV-like header


class TestTranscribeDispatcher:
    @patch("voice_agent.audio.transcribe.transcribe_groq", return_value="hello world")
    def test_groq_backend_called(self, mock_groq):
        result = transcribe(DUMMY_WAV, backend="groq", groq_api_key="fake-key")
        mock_groq.assert_called_once_with(DUMMY_WAV, "fake-key")
        assert result == "hello world"

    @patch("voice_agent.audio.transcribe.transcribe_local", return_value="local result")
    def test_local_backend_called(self, mock_local):
        result = transcribe(DUMMY_WAV, backend="local")
        mock_local.assert_called_once()
        assert result == "local result"

    @patch("voice_agent.audio.transcribe.transcribe_groq", side_effect=Exception("API down"))
    @patch("voice_agent.audio.transcribe.transcribe_local", return_value="fallback text")
    def test_groq_failure_falls_back_to_local(self, mock_local, mock_groq):
        result = transcribe(DUMMY_WAV, backend="groq", groq_api_key="fake-key")
        mock_local.assert_called_once()
        assert result == "fallback text"

    def test_unknown_backend_uses_local(self):
        with patch("voice_agent.audio.transcribe.transcribe_local", return_value="ok") as mock_local:
            result = transcribe(DUMMY_WAV, backend="unknown")
            assert result == "ok"


class TestCommandResolution:
    """Smoke-test voice macro resolution end-to-end."""

    def test_exit_macro(self):
        from voice_agent.agent.commands import resolve, is_exit
        assert resolve("exit") == "/exit"
        assert is_exit("exit session") is True

    def test_undo_macro(self):
        from voice_agent.agent.commands import resolve
        assert resolve("undo that") == "/undo"

    def test_plain_text_passthrough(self):
        from voice_agent.agent.commands import resolve
        msg = "create a python function to sort a list"
        assert resolve(msg) == msg

    def test_case_insensitive(self):
        from voice_agent.agent.commands import resolve
        assert resolve("EXIT") == "/exit"
        assert resolve("UNDO THAT") == "/undo"

    # ── aider native command macros ───────────────────────────────────────────

    def test_undo_variations(self):
        from voice_agent.agent.commands import resolve
        assert resolve("undo") == "/undo"
        assert resolve("revert") == "/undo"
        assert resolve("undo last change") == "/undo"

    def test_clear_macros(self):
        from voice_agent.agent.commands import resolve
        assert resolve("clear") == "/clear"
        assert resolve("clear history") == "/clear"
        assert resolve("start over") == "/clear"

    def test_ls_macros(self):
        from voice_agent.agent.commands import resolve
        assert resolve("list files") == "/ls"
        assert resolve("show files") == "/ls"
        assert resolve("what files") == "/ls"

    def test_diff_macros(self):
        from voice_agent.agent.commands import resolve
        assert resolve("show diff") == "/diff"
        assert resolve("what changed") == "/diff"
        assert resolve("diff") == "/diff"

    def test_commit_macros(self):
        from voice_agent.agent.commands import resolve
        assert resolve("commit") == "/commit"
        assert resolve("commit changes") == "/commit"
        assert resolve("save changes") == "/commit"

    # ── file add/drop regex ───────────────────────────────────────────────────

    def test_add_file_simple(self):
        from voice_agent.agent.commands import resolve
        assert resolve("add main.py") == "/add main.py"
        assert resolve("add utils.py") == "/add utils.py"

    def test_add_file_with_keyword(self):
        from voice_agent.agent.commands import resolve
        assert resolve("add file main.py") == "/add main.py"
        assert resolve("add the file utils.py") == "/add utils.py"

    def test_drop_file(self):
        from voice_agent.agent.commands import resolve
        assert resolve("drop main.py") == "/drop main.py"
        assert resolve("remove utils.py") == "/drop utils.py"
        assert resolve("remove the file main.py") == "/drop main.py"

    def test_add_file_with_path(self):
        from voice_agent.agent.commands import resolve
        assert resolve("add src/main.py") == "/add src/main.py"

    # ── trailing punctuation ─────────────────────────────────────────────────

    def test_trailing_punctuation_stripped(self):
        from voice_agent.agent.commands import resolve
        assert resolve("undo.") == "/undo"
        assert resolve("clear!") == "/clear"
        assert resolve("commit?") == "/commit"
