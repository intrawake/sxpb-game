import os
import subprocess
import sys
import json
import tempfile

# Paths
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SERVER_PY = os.path.join(REPO_ROOT, "src", "sxpb_game", "harness", "sxpb_game_main.py")


def test_logging_on_api_failure():
    """
    Regression test: Ensure that when an LLM fails to return content,
    the failure is still recorded in the history and verbose logs.
    """
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{REPO_ROOT}:{os.path.join(REPO_ROOT, 'src')}"

    # Define two bots: one that will trigger a simulated failure in server.py
    # and one that uses a random algorithm to ensure the game starts.
    players_sxpb = '(()) (() (name "Bot1") (model "non-existent-model")) (() (name "Bot2") (algorithm "random"))'
    model_by_name_sxpb = '() ("non-existent-model" (timeout 1))'

    with tempfile.TemporaryDirectory() as tmp_dir:
        history_file = os.path.join(tmp_dir, "history.sxpb")
        verbose_file = os.path.join(tmp_dir, "verbose.jsonl")

        cmd = [
            sys.executable,
            SERVER_PY,
            "--openai_api_url",
            "http://localhost:11434/v1",
            "--interactive",
            "--game",
            "tictactoe",
            "--players",
            players_sxpb,
            "--model_by_name",
            model_by_name_sxpb,
            "--rendezqueue_api_url",
            "http://localhost:0/",  # dummy URL
            "--log_sxpb",
            history_file,
            "--trace_jsonl",
            verbose_file,
        ]

        proc = subprocess.Popen(
            cmd,
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        import time

        time.sleep(5)
        try:
            assert proc.stdin is not None
            proc.stdin.write("quit\n")
            proc.stdin.flush()
            proc.communicate(timeout=10)
        except Exception:
            proc.kill()
            proc.communicate()

        # Check logs even if server failed (it's expected to fail after logging)
        if not os.path.exists(history_file) or not os.path.exists(verbose_file):
            print("FAIL: Log files not created.")
            sys.exit(1)

        with open(history_file, "r") as f:
            if '(invalid_turn (p 0) (txt ""))' not in f.read():
                print("FAIL: SxPB history missing the invalid_turn entry.")
                sys.exit(1)

        with open(verbose_file, "r") as f:
            log_entry = json.loads(f.readline())
            if log_entry["valid"] is not False or log_entry["txt"] is not None:
                print("FAIL: Verbose log entry incorrect.")
                sys.exit(1)

    print("PASS: Logging regression test successful.")


if __name__ == "__main__":
    test_logging_on_api_failure()
