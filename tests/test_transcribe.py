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

    # ── new command macros ────────────────────────────────────────────────────

    def test_save_macros(self):
        from voice_agent.agent.commands import resolve
        assert resolve("save") == "/save"
        assert resolve("save that") == "/save"
        assert resolve("save the code") == "/save"
        assert resolve("write to file") == "/save"

    def test_run_macros(self):
        from voice_agent.agent.commands import resolve
        assert resolve("run") == "/run"
        assert resolve("run that") == "/run"
        assert resolve("run the code") == "/run"
        assert resolve("execute that") == "/run"

    def test_ls_macros(self):
        from voice_agent.agent.commands import resolve
        assert resolve("list directory") == "/ls"
        assert resolve("show directory") == "/ls"
        assert resolve("what's here") == "/ls"

    # ── save-with-filename regex ──────────────────────────────────────────────

    def test_save_as_with_extension(self):
        from voice_agent.agent.commands import resolve
        assert resolve("save as main.py") == "/save main.py"
        assert resolve("save that as utils.py") == "/save utils.py"
        assert resolve("save to solution.py") == "/save solution.py"

    def test_save_as_infers_py_extension(self):
        from voice_agent.agent.commands import resolve
        assert resolve("save as main") == "/save main.py"
        assert resolve("save that as solution") == "/save solution.py"

    def test_save_as_strips_trailing_punctuation(self):
        from voice_agent.agent.commands import resolve
        assert resolve("save as main.py.") == "/save main.py"
        assert resolve("save that as utils.py!") == "/save utils.py"
        assert resolve("save as solution.py?") == "/save solution.py"

    def test_save_as_case_insensitive(self):
        from voice_agent.agent.commands import resolve
        assert resolve("Save That As Main.py") == "/save Main.py"
        assert resolve("SAVE AS UTILS.PY") == "/save UTILS.PY"

    def test_save_as_hyphenated_name(self):
        from voice_agent.agent.commands import resolve
        assert resolve("save as my-script.py") == "/save my-script.py"
