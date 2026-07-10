import os
import subprocess
import sys
import tempfile

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SERVER_PY = os.path.join(REPO_ROOT, "src", "sxpb_game", "harness", "sxpb_game_main.py")


def test_invalid_response_retry():
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{REPO_ROOT}:{os.path.join(REPO_ROOT, 'src')}"

    # Use 'invalid-response-model' which simulates returning a bad move string
    players_sxpb = '(()) (() (name "Bot1") (model "invalid-response-model")) (() (name "Bot2") (algorithm "random"))'
    # Dictionary format: () ("key" (subkey val))
    model_by_name_sxpb = '() ("invalid-response-model" (timeout 1))'

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
            "--retry_limit",
            "4",
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
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.PIPE,
            text=True,
            cwd=REPO_ROOT,
        )
        import time

        time.sleep(5)
        try:
            assert proc.stdin is not None
            proc.stdin.write("quit\n")
            proc.stdin.flush()
            stdout_output, _ = proc.communicate(timeout=10)
        except Exception:
            proc.kill()
            stdout_output, _ = proc.communicate()
        # Print output for debugging in the CI/environment
        print("Captured Output:")
        print(stdout_output)

        if "LLM provided invalid move" not in stdout_output:
            print("FAIL: Did not find invalid move logging.")
            sys.exit(1)

        invalid_responses_count = stdout_output.count("LLM provided invalid move")
        if invalid_responses_count != 4:
            print(
                f"FAIL: Expected 4 retries for invalid response, got {invalid_responses_count}."
            )
            print("Output was:")
            print(stdout_output)
            sys.exit(1)

        if not os.path.exists(verbose_file):
            print("FAIL: Log files not created.")
            sys.exit(1)

        import json

        with open(verbose_file, "r") as f:
            lines = f.readlines()
            if len(lines) < 4:
                print("FAIL: Expected at least 4 invalid attempts logged.")
                sys.exit(1)

            # Check that the repeated invalid responses caused the messages array to reset periodically
            for i, line in enumerate(lines):
                rec = json.loads(line)
                api_req = rec.get("api_request", {})
                messages = api_req.get("messages", [])

                expected_len = 1 if i % 2 == 0 else 3
                assert len(messages) == expected_len, (
                    f"Expected {expected_len} messages on attempt {i + 1}, got {len(messages)}"
                )

    print("PASS: Invalid response retry test successful.")


if __name__ == "__main__":
    test_invalid_response_retry()
