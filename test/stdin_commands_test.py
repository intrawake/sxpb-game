import sys
import os
import threading
from unittest.mock import patch

from test.helpers import wait_for_output

sys.path.insert(
    0,
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")),
)
from sxpb_game.harness import sxpb_game_main as server


import warnings

warnings.filterwarnings("ignore", message=".*Exception in thread.*")


def test_retry_command_interrupts_call_api():
    call_count = 0
    first_call_started = threading.Event()
    second_call_started = threading.Event()
    blocking_call = threading.Event()

    def mock_call_api(*args, **kwargs):
        nonlocal call_count
        call_count += 1

        if call_count == 1:
            first_call_started.set()
            while True:
                blocking_call.wait(0.01)
        else:
            second_call_started.set()
            return '```sxpb >/dev/stdout\n(answer "(0, 0)")\n```', None, None

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
        patch("sxpb_game.harness.sxpb_game_main.call_api", side_effect=mock_call_api),
        patch("sys.stdin", mock_stdin),
        patch("os._exit", side_effect=mock_exit),
        patch(
            "sys.argv",
            [
                "sxpb_game_main.py",
                "--interactive",
                "--game",
                "tictactoe",
                "--openai_api_url",
                "http://dummy/v1",
                "--players",
                '(()) (() (name "Bot1") (model "gpt-4")) (() (name "Bot2") (algorithm "random"))',
            ],
        ),
    ):
        server_thread = threading.Thread(target=server.main, daemon=True)
        server_thread.start()

        assert first_call_started.wait(timeout=5.0)
        assert call_count == 1

        mock_stdin.push("retry\n")

        assert second_call_started.wait(timeout=5.0)
        assert call_count >= 2

        mock_stdin.push("quit\n")
        server_thread.join(timeout=0.1)


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
        patch(
            "sxpb_game.harness.sxpb_game_main.call_api",
            return_value=('```sxpb >/dev/stdout\n(answer "a1")\n```', None, None),
        ),
        patch("sys.stdin", mock_stdin),
        patch("sys.stdout", mock_stdout),
        patch("os._exit", side_effect=mock_exit),
        patch(
            "sys.argv",
            [
                "sxpb_game_main.py",
                "--interactive",
                "--game",
                "tictactoe",
                "--openai_api_url",
                "http://dummy/v1",
                "--players",
                '(()) (() (model "gpt-4")) (() (model "gpt-4"))',
            ],
        ),
    ):
        server_thread = threading.Thread(target=server.main, daemon=True)
        server_thread.start()

        mock_stdin.push("help\n")
        mock_stdin.push("view\n")
        mock_stdin.push("prompt\n")
        mock_stdin.push("history\n")
        mock_stdin.push("quit\n")

        output = wait_for_output(mock_stdout, "Exiting server...")

        server_thread.join(timeout=0.1)

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
        patch(
            "sxpb_game.harness.sxpb_game_main.call_api",
            return_value=('```sxpb >/dev/stdout\n(answer "a1")\n```', None, None),
        ),
        patch("sys.stdin", mock_stdin),
        patch("sys.stdout", mock_stdout),
        patch("os._exit", side_effect=mock_exit),
        patch(
            "sys.argv",
            [
                "sxpb_game_main.py",
                "--interactive",
                "--game",
                "tictactoe",
                "--openai_api_url",
                "http://dummy/v1",
                "--players",
                '(()) (() (model "gpt-4")) (() (model "gpt-4"))',
            ],
        ),
    ):
        server_thread = threading.Thread(target=server.main, daemon=True)
        server_thread.start()

        # Suspend immediately
        mock_stdin.push("suspend\n")

        # Should see suspended message
        output = wait_for_output(
            mock_stdout, "Game will suspend after the current move."
        )
        assert "Game will suspend after the current move." in output

        # Resume
        mock_stdin.push("resume\n")

        # Should see resuming message
        output = wait_for_output(mock_stdout, "Resuming...")
        assert "Resuming..." in output

        mock_stdin.push("quit\n")
        wait_for_output(mock_stdout, "Exiting server...")
        server_thread.join(timeout=0.1)


def test_say_command():
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
        patch(
            "sxpb_game.harness.sxpb_game_main.call_api",
            side_effect=lambda *args, **kwargs: (
                '```sxpb >/dev/stdout\n(answer "a1")\n```',
                None,
                None,
            ),
        ),
        patch("sys.stdin", mock_stdin),
        patch("sys.stdout", mock_stdout),
        patch("os._exit", side_effect=mock_exit),
        patch(
            "sys.argv",
            [
                "sxpb_game_main.py",
                "--interactive",
                "--game",
                "tictactoe",
                "--openai_api_url",
                "http://dummy/v1",
                "--players",
                '(()) (() (model "gpt-4")) (() (model "gpt-4"))',
            ],
        ),
    ):
        mock_stdin.push("suspend 0 -1\n")
        server_thread = threading.Thread(target=server.main, daemon=True)
        server_thread.start()

        wait_for_output(mock_stdout, "Game is suspended for Player 0.")
        mock_stdout.truncate(0)
        mock_stdout.seek(0)

        # Say command when paused with invalid move
        mock_stdin.push("say invalid_move\n")

        output = wait_for_output(mock_stdout, "Invalid say move 'invalid_move':")
        assert "Invalid say move 'invalid_move':" in output
        assert "Resuming..." not in output  # Game should still be paused

        mock_stdout.truncate(0)
        mock_stdout.seek(0)

        # Say command with valid move
        mock_stdin.push("say a1\n")

        output = wait_for_output(mock_stdout, "Say move accepted for Player 0: a1")
        assert "Say move accepted for Player 0: a1" in output
        assert "Resuming..." in output

        mock_stdin.push("quit\n")
        wait_for_output(mock_stdout, "Exiting server...")
        server_thread.join(timeout=0.1)


def test_suspend_with_count_command():
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
        patch(
            "sxpb_game.harness.sxpb_game_main.call_api",
            return_value=('```sxpb >/dev/stdout\n(answer "a1")\n```', None, None),
        ),
        patch("sys.stdin", mock_stdin),
        patch("sys.stdout", mock_stdout),
        patch("os._exit", side_effect=mock_exit),
        patch(
            "sys.argv",
            [
                "sxpb_game_main.py",
                "--interactive",
                "--game",
                "tictactoe",
                "--openai_api_url",
                "http://dummy/v1",
                "--players",
                '(()) (() (model "gpt-4")) (() (model "gpt-4"))',
            ],
        ),
    ):
        server_thread = threading.Thread(target=server.main, daemon=True)
        server_thread.start()

        # Suspend player 0 for 2 moves
        mock_stdin.push("suspend 0 2\n")
        wait_for_output(
            mock_stdout,
            "Game will suspend the next 2 times Player 0 is about to move.",
        )

        # Clear suspension
        mock_stdin.push("suspend 0 0\n")
        wait_for_output(mock_stdout, "Suspension cleared for Player 0.")

        # Suspend player 1 indefinitely
        mock_stdin.push("suspend 1\n")
        wait_for_output(
            mock_stdout,
            "Game will suspend the next time Player 1 is about to move.",
        )

        # Resume player 1
        mock_stdin.push("resume 1\n")
        wait_for_output(mock_stdout, "Resuming Player 1...")

        mock_stdin.push("quit\n")
        output = wait_for_output(mock_stdout, "Exiting server...")
        server_thread.join(timeout=0.1)
        assert "Game will suspend the next 2 times Player 0 is about to move." in output
        assert "Suspension cleared for Player 0." in output
        assert "Game will suspend the next time Player 1 is about to move." in output
        assert "Resuming Player 1..." in output


def test_resume_preserves_player_suspension():
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

    call_count = 0

    def mock_call_api(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count % 2 == 1:
            return '```sxpb >/dev/stdout\n(answer "a1")\n```', None, None
        else:
            return '```sxpb >/dev/stdout\n(answer "b2")\n```', None, None

    with (
        patch("sxpb_game.harness.sxpb_game_main.call_api", side_effect=mock_call_api),
        patch("sys.stdin", mock_stdin),
        patch("sys.stdout", mock_stdout),
        patch("os._exit", side_effect=mock_exit),
        patch(
            "sys.argv",
            [
                "sxpb_game_main.py",
                "--interactive",
                "--game",
                "tictactoe",
                "--openai_api_url",
                "http://dummy/v1",
                "--players",
                '(()) (() (model "gpt-4")) (() (model "gpt-4"))',
            ],
        ),
    ):
        # Push suspend before the thread even starts
        mock_stdin.push("suspend 0 2\n")

        server_thread = threading.Thread(target=server.main, daemon=True)
        server_thread.start()

        # It should log that it is suspended for P0
        output = wait_for_output(mock_stdout, "Game is suspended for Player 0.")
        assert "Game will suspend the next 2 times Player 0 is about to move." in output
        assert "Game is suspended for Player 0." in output

        # Clear stdout
        mock_stdout.truncate(0)
        mock_stdout.seek(0)

        # Resume globally. This should decrement P0's suspension count to 1,
        # unblock P0 for the current move, let P1 move, and then when it's P0's turn again,
        # it should suspend AGAIN because P0 had a count of 2.
        mock_stdin.push("resume\n")

        output = wait_for_output(mock_stdout, "Game is suspended for Player 0.")
        assert "Resuming..." in output
        assert "Game is suspended for Player 0." in output

        mock_stdin.push("quit\n")
        wait_for_output(mock_stdout, "Exiting server...")
        server_thread.join(timeout=0.1)
