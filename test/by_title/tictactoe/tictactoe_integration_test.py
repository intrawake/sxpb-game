"""Actual command processes hand off across turns, expiry, and game shutdown."""

from contextlib import closing
import os
import shlex
import socket
import subprocess
import sys
import time
import uuid

import pytest

from test.helpers import read_until, wait_for_port

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SERVER_DIR = os.path.join(REPO_ROOT, "src", "sxpb_game", "harness")
SERVER_PY = os.path.join(SERVER_DIR, "sxpb_game_main.py")
CLIENT_PY = os.path.join(SERVER_DIR, "client.py")


@pytest.fixture
def env():
    return dict(
        os.environ, PYTHONPATH=f"{REPO_ROOT}:{REPO_ROOT}/src", PYTHONUNBUFFERED="1"
    )


@pytest.fixture
def rendezqueue_server():
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.bind(("", 0))
        port = sock.getsockname()[1]
    url = f"http://127.0.0.1:{port}/"
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "rendezqueue.server",
            "--http_host",
            "127.0.0.1",
            "--http_port",
            str(port),
            "--plyswap_ttl",
            "1",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        wait_for_port(port, process=process)
        yield url
    finally:
        process.terminate()
        process.communicate(timeout=5)


def continuation(output):
    lines = [line for line in output.splitlines() if line.startswith("Continue with: ")]
    assert len(lines) == 1, output
    arguments = shlex.split(lines[0].removeprefix("Continue with: "))
    assert len(arguments) == 4 and arguments[::2] == ["--self", "--peer"]
    return arguments


def test_tictactoe_integration(env, rendezqueue_server):
    url = rendezqueue_server
    key = "game-" + uuid.uuid4().hex
    processes = []
    server = subprocess.Popen(
        [
            sys.executable,
            SERVER_PY,
            "--rendezqueue_api_url",
            url,
            "--key",
            key,
            "--openai_api_url",
            "http://localhost:11434/v1",
            "--game",
            "tictactoe",
        ],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    logs = []

    def command(player, *arguments):
        process = subprocess.Popen(
            [
                sys.executable,
                CLIENT_PY,
                "--rendezqueue_api_url",
                url,
                "--key",
                f"{key}_{player}",
                *arguments,
            ],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        processes.append(process)
        return process

    def completed(process):
        output, errors = process.communicate(timeout=20)
        assert process.returncode == 0, f"{output}\n{errors}"
        return output

    def accepted(player, move):
        assert server.stdout is not None
        logs.append(
            read_until(
                server.stdout, f"Move accepted from {player}: {move}", timeout=20
            )
        )

    try:
        assert server.stdout is not None
        logs.append(read_until(server.stdout, "Server is live"))
        x1 = command("X", "--move", "b2")
        accepted("X", "b2")
        # Separate status command exits; its cursor is all the next process gets.
        status = completed(command("O", "--status"))
        assert "You are: O" in status and "Current Player: O" in status
        first_o_cursor = continuation(status)
        # The command's cached row expires while the authoritative peer remains live.
        time.sleep(1.25)
        o1 = command("O", *first_o_cursor, "--move", "a1")
        accepted("O", "a1")
        x1_output = completed(x1)
        assert "Current Board:" in x1_output
        x_cursor = continuation(x1_output)
        assert x_cursor != first_o_cursor

        x2 = command("X", *x_cursor, "--move", "a2")
        accepted("X", "a2")
        o_cursor = continuation(completed(o1))
        assert o_cursor != first_o_cursor
        o2 = command("O", *o_cursor, "--move", "b1")
        accepted("O", "b1")
        x_cursor2 = continuation(completed(x2))
        assert x_cursor2 != x_cursor
        x3 = command("X", *x_cursor2, "--move", "c2")
        accepted("X", "c2")
        for process in (o2, x3):
            output = completed(process)
            assert "Game Over! Winner: X" in output
            assert "Continue with:" not in output
        output, errors = server.communicate(timeout=10)
        logs.append(output)
        assert server.returncode == 0, errors
        assert "All players received final state. Shutting down now." in output
        entire_log = "".join(logs)
        for player, move in [
            ("X", "b2"),
            ("O", "a1"),
            ("X", "a2"),
            ("O", "b1"),
            ("X", "c2"),
        ]:
            assert entire_log.count(f"Move accepted from {player}: {move}") == 1
        assert all(process.poll() == 0 for process in processes)
    finally:
        # Cleanup is only for failures; success above requires every process to exit.
        for process in [*processes, server]:
            if process.poll() is None:
                process.kill()
            process.communicate(timeout=5)
