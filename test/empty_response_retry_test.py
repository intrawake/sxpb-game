import os
import subprocess
import sys
import tempfile

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SERVER_PY = os.path.join(REPO_ROOT, "src", "sxpb_game", "harness", "sxpb_game_main.py")


def test_empty_response_retry():
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{REPO_ROOT}:{os.path.join(REPO_ROOT, 'src')}"

    # Use 'empty-response-model' which simulates returning empty string
    players_sxpb = '(()) (() (name "Bot1") (model "empty-response-model")) (() (name "Bot2") (algorithm "random"))'
    # Dictionary format: () ("key" (subkey val))
    model_by_name_sxpb = '() ("empty-response-model" (timeout 1))'

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
            "--verbose_log_jsonl",
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

        if "LLM provided empty response for player" not in stdout_output:
            print("FAIL: Did not find empty response logging.")
            sys.exit(1)

        empty_responses_count = stdout_output.count("LLM provided empty response")
        if empty_responses_count != 4:
            print(
                f"FAIL: Expected 4 retries for empty response, got {empty_responses_count}."
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

            # Empty responses reset to clean prompt every time, so each
            # attempt should see exactly 1 message (the original prompt).
            for i, line in enumerate(lines):
                rec = json.loads(line)
                api_req = rec.get("api_request", {})
                messages = api_req.get("messages", [])

                assert len(messages) == 1, (
                    f"Expected 1 message on attempt {i + 1}, got {len(messages)}"
                )

                for j, msg in enumerate(messages):
                    if (
                        msg.get("role") == "assistant"
                        and not msg.get("content", "").strip()
                    ):
                        print(
                            f"FAIL: Empty assistant found in verbose log "
                            f"entry {i}, index {j}."
                        )
                        sys.exit(1)

    print("PASS: Empty response retry test successful.")


if __name__ == "__main__":
    test_empty_response_retry()
