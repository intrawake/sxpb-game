import sys
import os
import threading
import time
from unittest.mock import patch

sys.path.insert(0, os.path.abspath("server"))
import server


import warnings

warnings.filterwarnings("ignore", message=".*Exception in thread.*")


def test_retry_command_interrupts_call_api():
    call_count = 0

    def mock_call_api(*args, **kwargs):
        nonlocal call_count
        call_count += 1

        if call_count == 1:
            while True:
                time.sleep(0.1)
        else:
            return '(answer "(0, 0)")', None, None

    class MockStdin:
        def __init__(self):
            self.lines = []
            self.lock = threading.Lock()
            self.cond = threading.Condition(self.lock)
            self.closed = False

        def push(self, line):
            with self.lock:
                self.lines.append(line)
                self.cond.notify()

        def close(self):
            with self.lock:
                self.closed = True
                self.cond.notify_all()

        def __iter__(self):
            return self

        def __next__(self):
            with self.lock:
                while not self.lines and not self.closed:
                    self.cond.wait()
                if self.lines:
                    return self.lines.pop(0)
                raise StopIteration

    mock_stdin = MockStdin()

    def mock_exit(code):
        # Do nothing. The thread will finish its execution path naturally or block
        # on daemon tasks (like waiting for stdin), avoiding UnhandledThreadException.
        pass

    with (
        patch("server.call_api", side_effect=mock_call_api),
        patch("sys.stdin", mock_stdin),
        patch("os._exit", side_effect=mock_exit),
        patch(
            "sys.argv",
            [
                "server.py",
                "--game",
                "tictactoe",
                "--openai_api_url",
                "http://dummy/v1",
                "--players",
                '(()) (() (name "Bot1") (model "gpt-4")) (() (name "Bot2") (algorithm "random"))',
            ],
        ),
    ):
        server_thread = threading.Thread(target=server.main, daemon=True)  # type: ignore
        server_thread.start()

        time.sleep(1.0)
        assert call_count == 1

        mock_stdin.push("retry\n")

        time.sleep(1.0)
        assert call_count >= 2

        mock_stdin.push("quit\n")
        server_thread.join(timeout=2.0)


def test_view_prompt_history_commands():
    import io

    class MockStdin:
        def __init__(self):
            self.lines = []
            self.lock = threading.Lock()
            self.cond = threading.Condition(self.lock)
            self.closed = False

        def push(self, line):
            with self.lock:
                self.lines.append(line)
                self.cond.notify()

        def close(self):
            with self.lock:
                self.closed = True
                self.cond.notify_all()

        def __iter__(self):
            return self

        def __next__(self):
            with self.lock:
                while not self.lines and not self.closed:
                    self.cond.wait()
                if self.lines:
                    return self.lines.pop(0)
                raise StopIteration

    mock_stdin = MockStdin()
    mock_stdout = io.StringIO()

    def mock_exit(code):
        pass

    with (
        patch("server.call_api", return_value=('(answer "a1")', None, None)),
        patch("sys.stdin", mock_stdin),
        patch("sys.stdout", mock_stdout),
        patch("os._exit", side_effect=mock_exit),
        patch(
            "sys.argv",
            [
                "server.py",
                "--game",
                "tictactoe",
                "--openai_api_url",
                "http://dummy/v1",
                "--players",
                "((model gpt-4)) ((model gpt-4))",
            ],
        ),
    ):
        server_thread = threading.Thread(target=server.main, daemon=True)  # type: ignore
        server_thread.start()

        # Give it a moment to start and maybe take a turn
        time.sleep(1.0)

        mock_stdin.push("help\n")
        mock_stdin.push("view\n")
        mock_stdin.push("prompt\n")
        mock_stdin.push("history\n")
        mock_stdin.push("quit\n")

        server_thread.join(timeout=3.0)

        output = mock_stdout.getvalue()

        # Verify bits of expected output
        assert "Supported commands:" in output
        assert "--- View for Player 0" in output
        assert "--- Prompt for Player" in output
        assert "--- Move History ---" in output
        assert "Exiting server..." in output


def test_suspend_resume_commands():
    import io

    class MockStdin:
        def __init__(self):
            self.lines = []
            self.lock = threading.Lock()
            self.cond = threading.Condition(self.lock)
            self.closed = False

        def push(self, line):
            with self.lock:
                self.lines.append(line)
                self.cond.notify()

        def close(self):
            with self.lock:
                self.closed = True
                self.cond.notify_all()

        def __iter__(self):
            return self

        def __next__(self):
            with self.lock:
                while not self.lines and not self.closed:
                    self.cond.wait()
                if self.lines:
                    return self.lines.pop(0)
                raise StopIteration

    mock_stdin = MockStdin()
    mock_stdout = io.StringIO()

    def mock_exit(code):
        pass

    with (
        patch("server.call_api", return_value=('(answer "a1")', None, None)),
        patch("sys.stdin", mock_stdin),
        patch("sys.stdout", mock_stdout),
        patch("os._exit", side_effect=mock_exit),
        patch(
            "sys.argv",
            [
                "server.py",
                "--game",
                "tictactoe",
                "--openai_api_url",
                "http://dummy/v1",
                "--players",
                "((model gpt-4)) ((model gpt-4))",
            ],
        ),
    ):
        server_thread = threading.Thread(target=server.main, daemon=True)  # type: ignore
        server_thread.start()

        # Suspend immediately
        mock_stdin.push("suspend\n")
        time.sleep(1.0)

        # Should see suspended message
        output = mock_stdout.getvalue()
        assert "Game will suspend after the current move." in output

        # Resume
        mock_stdin.push("resume\n")
        time.sleep(1.0)

        # Should see resuming message
        output = mock_stdout.getvalue()
        assert "Resuming all..." in output

        mock_stdin.push("quit\n")
        server_thread.join(timeout=3.0)
