import os
import subprocess
import sys
import time

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SERVER_PY = os.path.join(REPO_ROOT, "src", "sxpb_game", "harness", "sxpb_game_main.py")


def test_server_no_llm_no_api_url():
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{REPO_ROOT}:{os.path.join(REPO_ROOT, 'src')}"

    # Two human players, no LLMs
    players_sxpb = "(()) (())"

    cmd = [
        sys.executable,
        SERVER_PY,
        "--game",
        "tictactoe",
        "--players",
        players_sxpb,
    ]

    try:
        proc = subprocess.Popen(
            cmd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=REPO_ROOT,
        )

        # If it's still alive after 2 seconds, it means it successfully parsed args
        time.sleep(2)
        if proc.poll() is None:
            proc.terminate()
            print(
                "PASS: Server started successfully without --openai_api_url for human-only game."
            )
        else:
            stdout, _ = proc.communicate()
            print("FAIL: Server exited unexpectedly with output:")
            print(stdout)
            sys.exit(1)

    except Exception as e:
        print(f"FAIL: Unexpected error: {e}")
        sys.exit(1)


def test_server_with_llm_no_api_url():
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{REPO_ROOT}:{os.path.join(REPO_ROOT, 'src')}"

    # One LLM player
    players_sxpb = '(()) (() (model "gpt-4"))'

    cmd = [
        sys.executable,
        SERVER_PY,
        "--game",
        "tictactoe",
        "--players",
        players_sxpb,
        # No --openai_api_url
    ]

    try:
        proc = subprocess.Popen(
            cmd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=REPO_ROOT,
        )

        # It should check the LLM status on startup and exit immediately with an error
        start_time = time.time()
        exited = False
        while time.time() - start_time < 5:
            if proc.poll() is not None:
                exited = True
                break
            time.sleep(0.5)

        if not exited:
            proc.terminate()
            print(
                "FAIL: Server should have exited with an error when an LLM is used without --openai_api_url."
            )
            sys.exit(1)

        stdout, _ = proc.communicate()
        if "is an LLM, but --openai_api_url was not provided" in stdout:
            print("PASS: Server correctly errored out when LLM used without API URL.")
        else:
            print("FAIL: Server exited with wrong error message:")
            print(stdout)
            sys.exit(1)

    except Exception as e:
        print(f"FAIL: Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    test_server_no_llm_no_api_url()
    test_server_with_llm_no_api_url()
