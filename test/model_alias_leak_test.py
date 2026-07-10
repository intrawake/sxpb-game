import os
import subprocess
import sys
import tempfile
import time
import json

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SERVER_PY = os.path.join(REPO_ROOT, "src", "sxpb_game", "harness", "sxpb_game_main.py")


def test_fullname_not_treated_as_alias():
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{REPO_ROOT}:{os.path.join(REPO_ROOT, 'src')}"

    # We use "non-existent-model" as our "real" fullname.
    # The server has a built-in shortcut that skips call_api for this string.
    # If the leak exists, it will resolve to "my-alias" and attempt a network call.
    # If the fix works, it will stay "non-existent-model" and skip the network call.
    model_by_name_sxpb = '("my-alias" (fullname "non-existent-model"))'
    players_sxpb = '(()) (() (model "non-existent-model")) (() (algorithm "random"))'

    with tempfile.TemporaryDirectory() as tmp_dir:
        verbose_file = os.path.join(tmp_dir, "verbose.jsonl")

        cmd = [
            sys.executable,
            SERVER_PY,
            "--openai_api_url",
            "http://localhost:0/v1",
            "--game",
            "tictactoe",
            "--players",
            players_sxpb,
            "--model_by_name",
            model_by_name_sxpb,
            "--trace_jsonl",
            verbose_file,
            "--retry_limit",
            "1",
        ]

        proc = subprocess.Popen(
            cmd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=REPO_ROOT,
        )

        # Give it a moment to resolve the model.
        # Since "non-existent-model" is a no-op, it should finish almost instantly.
        start_time = time.time()
        while time.time() - start_time < 5:
            if proc.poll() is not None:
                break
            time.sleep(0.1)

        if proc.poll() is None:
            proc.terminate()

        stdout_output, _ = proc.communicate()

        # Verify no network error leaked into stdout
        if "Connection refused" in stdout_output or "URL Error" in stdout_output:
            print(
                "FAIL: A network request was attempted! The fullname was likely aliased."
            )
            print(stdout_output)
            sys.exit(1)

        if not os.path.exists(verbose_file):
            print(f"FAIL: Verbose log {verbose_file} not created.")
            sys.exit(1)

        with open(verbose_file, "r") as f:
            lines = f.readlines()
            if not lines:
                print("FAIL: Verbose log is empty.")
                sys.exit(1)

            entry = json.loads(lines[0])
            resolved_model = entry.get("model")

        print("Requested model: non-existent-model")
        print(f"Resolved model in logs: {resolved_model}")

        if resolved_model != "non-existent-model":
            print(f"FAIL: Unexpected model name resolved: {resolved_model}")
            sys.exit(1)

    print("PASS: The full name was correctly preserved and no network call was made.")


if __name__ == "__main__":
    test_fullname_not_treated_as_alias()
