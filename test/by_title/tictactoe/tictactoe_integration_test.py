import os
import subprocess
import sys
import time
import pytest
import socket
from contextlib import closing

# Paths
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
TIC_TAC_TOE_DIR = os.path.join(REPO_ROOT, "tictactoe")
SERVER_DIR = os.path.join(REPO_ROOT, "src", "sxpb_game", "harness")
SERVER_PY = os.path.join(SERVER_DIR, "sxpb_game_main.py")
CLIENT_PY = os.path.join(SERVER_DIR, "client.py")


def find_free_port():
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("", 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]


@pytest.fixture
def env():
    e = os.environ.copy()
    # Ensure src and game root are in PYTHONPATH
    e["PYTHONPATH"] = f"{REPO_ROOT}:{os.path.join(REPO_ROOT, 'src')}"
    return e


@pytest.fixture
def rendezqueue_server():
    port = find_free_port()
    url = f"http://127.0.0.1:{port}/"

    # Start the python rendezqueue server locally for the test
    cmd = [
        sys.executable,
        "-m",
        "rendezqueue.server",
        "--http_host",
        "127.0.0.1",
        "--http_port",
        str(port),
    ]
    server_proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )

    # Give it a moment to bind and start listening
    time.sleep(2)
    if server_proc.poll() is not None:
        out, err = server_proc.communicate()
        raise RuntimeError(
            f"Rendezqueue server failed to start (code {server_proc.returncode}).\nSTDOUT: {out}\nSTDERR: {err}"
        )

    yield url

    server_proc.terminate()
    server_proc.wait(timeout=2)


def test_tictactoe_integration(env, rendezqueue_server):
    """
    Integration test for server and client.
    Spins up a local Rendezqueue service just for the test.
    """
    url = rendezqueue_server
    lobby_key = f"test_game_{int(time.time())}"

    # Start the authoritative server
    server_proc = subprocess.Popen(
        [
            sys.executable,
            SERVER_PY,
            "--rendezqueue_api_url",
            url,
            "--key",
            lobby_key,
            "--openai_api_url",
            "http://localhost:11434/v1",
            "--game",
            "tictactoe",
        ],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,  # Line buffered
    )

    try:
        # Give the server a moment to start and connect to Rendezqueue
        time.sleep(3)

        # Player keys
        x_key = f"{lobby_key}_X"
        o_key = f"{lobby_key}_O"

        # 1. Player X joins and makes a move
        x_proc1 = subprocess.Popen(
            [
                sys.executable,
                CLIENT_PY,
                "--rendezqueue_api_url",
                url,
                "--key",
                x_key,
                "--move",
                "b2",
            ],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        # Give it a second to connect and send the move
        time.sleep(1.5)

        # 2. Player O joins and checks status (without making a move)
        o_res1 = subprocess.run(
            [
                sys.executable,
                CLIENT_PY,
                "--rendezqueue_api_url",
                url,
                "--key",
                o_key,
                "--status",
            ],
            env=env,
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert o_res1.returncode == 0
        assert "You are: O" in o_res1.stdout
        assert "Current Player: O" in o_res1.stdout
        assert "X" in o_res1.stdout  # Board should show X's move

        # 3. Player O makes a move.
        o_proc2 = subprocess.Popen(
            [
                sys.executable,
                CLIENT_PY,
                "--rendezqueue_api_url",
                url,
                "--key",
                o_key,
                "--move",
                "a1",
            ],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        # Now that O has moved, X's blocking client should realize it is its turn again
        # and exit.
        try:
            x_out, x_err = x_proc1.communicate(timeout=15)
        except subprocess.TimeoutExpired:
            x_proc1.kill()
            x_out, x_err = x_proc1.communicate()
            assert False, f"Player X timed out waiting for its turn again. Out: {x_out}"

        assert x_proc1.returncode == 0
        assert "Current Board:" in x_out

        # O's process should also exit cleanly now that its move is confirmed,
        # but it will block waiting for X. Let's kill it so the test can finish.
        o_proc2.kill()

    finally:
        server_proc.terminate()
        server_proc.wait()
