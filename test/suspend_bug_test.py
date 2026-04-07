import sys
import os
import threading
import time
from unittest.mock import patch

sys.path.insert(0, os.path.abspath("server"))
import server

import warnings

warnings.filterwarnings("ignore", message=".*Exception in thread.*")


def test_say_command_resumed_players_bug():
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
        # P0 turn -> P1 turn -> P0 turn
        # P0 first turn is a say command
        # P1 first turn is LLM (a2)
        # P0 second turn should be suspended! If it's not, it will call API and return a3.
        if call_count == 1:
            return '(answer "a2")', None, None
        else:
            return '(answer "a3")', None, None

    with (
        patch("server.call_api", side_effect=mock_call_api),
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
                '(()) (() (model "gpt-4")) (() (model "gpt-4"))',
            ],
        ),
    ):
        server_thread = threading.Thread(target=server.main, daemon=True)  # type: ignore
        server_thread.start()

        # Suspend player 0 for 99 moves
        mock_stdin.push("suspend 0 99\n")
        time.sleep(1.0)

        output = mock_stdout.getvalue()
        assert (
            "Game will suspend the next 99 times Player 0 is about to move." in output
        )
        assert "Game is suspended for Player 0." in output

        mock_stdout.truncate(0)
        mock_stdout.seek(0)

        # Now P0 is suspended. We use 'say' to make a move for P0.
        mock_stdin.push("say a1\n")
        time.sleep(
            1.0
        )  # wait for say to process, then P1 to move, then it comes back to P0

        output = mock_stdout.getvalue()
        # It should say move accepted for P0
        assert "Say move accepted for Player 0: a1" in output
        # Then LLM move accepted from P1 (which is index 1, but player string might be "1" or whatever)
        assert "LLM Move accepted from O: a2" in output

        # THEN it should suspend for P0 again!
        assert "Game is suspended for Player 0." in output
        # It should NOT have accepted LLM move a3 from P0!
        assert "LLM Move accepted from X: a3" not in output

        mock_stdin.push("quit\n")
        server_thread.join(timeout=3.0)
