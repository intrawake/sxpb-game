import os
import subprocess
import sys
import tempfile
import time

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SERVER_PY = os.path.join(REPO_ROOT, "src", "sxpb_game", "harness", "sxpb_game_main.py")


def test_non_interactive_termination_on_invalid_format():
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{REPO_ROOT}:{os.path.join(REPO_ROOT, 'src')}"

    # Use 'empty-response-model' which simulates returning empty string
    players_sxpb = '(()) (() (name "Bot1") (model "empty-response-model")) (() (name "Bot2") (algorithm "random"))'
    model_by_name_sxpb = '() ("empty-response-model" (timeout 1))'

    with tempfile.TemporaryDirectory() as tmp_dir:
        history_file = os.path.join(tmp_dir, "history.sxpb")
        verbose_file = os.path.join(tmp_dir, "verbose.jsonl")

        cmd = [
            sys.executable,
            SERVER_PY,
            "--openai_api_url",
            "http://localhost:11434/v1",
            "--game",
            "tictactoe",
            "--retry_limit",
            "2",
            "--players",
            players_sxpb,
            "--model_by_name",
            model_by_name_sxpb,
            "--rendezqueue_api_url",
            "http://localhost:0/",
            "--log_sxpb",
            history_file,
            "--trace_jsonl",
            verbose_file,
        ]
        # Notice we are NOT passing --interactive

        proc = subprocess.Popen(
            cmd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.PIPE,
            text=True,
            cwd=REPO_ROOT,
        )

        # Give it some time to fail repeatedly.
        # It should try 3 times (initial + 2 retries) and then it should TERMINATE
        # rather than entering an infinite loop because --interactive is not provided.
        start_time = time.time()
        terminated = False
        while time.time() - start_time < 10:
            if proc.poll() is not None:
                terminated = True
                break
            time.sleep(0.5)

        if not terminated:
            proc.kill()
            stdout_output, _ = proc.communicate()
            print("Captured Output:")
            print(stdout_output)
            print(
                "FAIL: Server did not terminate on its own after repeated failures without --interactive."
            )
            sys.exit(1)

        stdout_output, _ = proc.communicate()

        if "LLM Move failed repeatedly" not in stdout_output:
            print("Captured Output:")
            print(stdout_output)
            print("FAIL: Did not find 'LLM Move failed repeatedly' in output.")
            sys.exit(1)

        # Ensure it actually exited with a failure code, not a success
        if proc.returncode == 0:
            print("FAIL: Server terminated but returned 0 instead of a failure code.")
            sys.exit(1)

        print("PASS: Server terminated correctly when non-interactive.")


if __name__ == "__main__":
    test_non_interactive_termination_on_invalid_format()
