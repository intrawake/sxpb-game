import os
import subprocess
import sys
import time
import pytest
import socket
import signal
from contextlib import closing

# Paths
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SERVER_DIR = os.path.join(REPO_ROOT, "src", "sxpb_game", "harness")
SERVER_PY = os.path.join(SERVER_DIR, "sxpb_game_main.py")


def find_free_port():
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("", 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]


@pytest.fixture
def env():
    e = os.environ.copy()
    e["PYTHONPATH"] = f"{REPO_ROOT}:{os.path.join(REPO_ROOT, 'src')}"
    return e


@pytest.fixture
def rendezqueue_server():
    port = find_free_port()
    url = f"http://127.0.0.1:{port}/"

    cmd = [
        sys.executable,
        "-m",
        "rendezqueue.server",
        "--http_host",
        "127.0.0.1",
        "--http_port",
        str(port),
    ]

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    time.sleep(1)  # Wait for server to start
    yield url

    proc.terminate()
    proc.wait()


def test_server_interrupt_clean_exit_and_save(env, rendezqueue_server, tmp_path):
    url = rendezqueue_server
    lobby_key = f"test_interrupt_{int(time.time())}"
    log_file = tmp_path / "test_log.sxpb"

    # Start the game server
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
            "--log_sxpb",
            str(log_file),
        ],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    # Let the server initialize and connect to rendezqueue
    time.sleep(2)

    # Send first SIGINT
    server_proc.send_signal(signal.SIGINT)

    # Wait a tiny bit and send a second SIGINT (simulate double-tap Ctrl+C)
    time.sleep(0.1)

    # We must check if the process is still alive before sending the second signal
    if server_proc.poll() is None:
        server_proc.send_signal(signal.SIGINT)

    # Wait for the server to exit
    try:
        stdout, stderr = server_proc.communicate(timeout=5)
    except subprocess.TimeoutExpired:
        server_proc.kill()
        stdout, stderr = server_proc.communicate()
        assert False, "Server did not exit within timeout after SIGINT"

    print("STDOUT:", stdout)
    print("STDERR:", stderr)

    # 1. Check clean exit
    assert server_proc.returncode == 0, (
        f"Expected return code 0 on SIGINT, got {server_proc.returncode}"
    )

    # 2. Check no stack trace
    assert "Traceback" not in stderr, "Found stack trace in stderr after SIGINT"
    assert "KeyboardInterrupt" not in stderr, (
        "Found unhandled KeyboardInterrupt in stderr"
    )

    # 3. Check file is written
    assert log_file.exists(), "Log file was not written after Ctrl+C!"
