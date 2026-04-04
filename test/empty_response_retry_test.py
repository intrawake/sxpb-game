import os
import subprocess
import sys
import tempfile

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SERVER_PY = os.path.join(REPO_ROOT, "server", "server.py")


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
            "pdm",
            "run",
            "python3",
            SERVER_PY,
            "--openai_api_url",
            "http://localhost:11434/v1",
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
            "--verbose_log_jsonl",
            verbose_file,
        ]

        # The server will retry 3 times, log the empty failures, and then exit with code 1.
        result = subprocess.run(
            cmd, env=env, capture_output=True, text=True, timeout=30, cwd=REPO_ROOT
        )

        stdout_output = result.stdout + result.stderr
        # Print output for debugging in the CI/environment
        print("Captured Output:")
        print(stdout_output)

        if "LLM provided empty response for player" not in stdout_output:
            print("FAIL: Did not find empty response logging.")
            sys.exit(1)

        empty_responses_count = stdout_output.count("LLM provided empty response")
        if empty_responses_count != 3:
            print(
                f"FAIL: Expected 3 retries for empty response, got {empty_responses_count}."
            )
            print("Output was:")
            print(stdout_output)
            sys.exit(1)

        if not os.path.exists(verbose_file):
            print("FAIL: Log files not created.")
            sys.exit(1)

        with open(verbose_file, "r") as f:
            lines = f.readlines()
            if len(lines) < 3:
                print("FAIL: Expected at least 3 invalid attempts logged.")
                sys.exit(1)

    print("PASS: Empty response retry test successful.")


if __name__ == "__main__":
    test_empty_response_retry()
