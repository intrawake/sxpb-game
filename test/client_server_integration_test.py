import os
import subprocess
import sys
import time
import pytest
import socket
from contextlib import closing

from test.helpers import read_until, wait_for_port

# Paths
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
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
    e["PYTHONPATH"] = f"{REPO_ROOT}:{os.path.join(REPO_ROOT, 'src')}"
    e["PYTHONUNBUFFERED"] = "1"
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
    server_proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )

    wait_for_port(port, process=server_proc)

    yield url

    server_proc.terminate()
    server_proc.wait(timeout=2)


def test_server_print_model(env, rendezqueue_server):
    url = rendezqueue_server
    lobby_key = f"test_game_{int(time.time())}"

    # Start server with one player as a model and another as name
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
            "--players",
            '(()) (() (model "fake_model") (premoves (()) "a1")) (() (name "Bob"))',
        ],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    assert server_proc.stdout is not None
    output_prefix = read_until(server_proc.stdout, "Server is live")
    server_proc.terminate()
    out, err = server_proc.communicate()
    out = output_prefix + out

    # Check that it properly prints the model line, not the client command
    assert "Player X managed by LLM:" in out
    assert "fake_model" in out
    # Check that it prints the client command for Bob
    assert (
        f"Player O (Bob) command: pdm run client --rendezqueue_api_url {url} --key {lobby_key}_O"
        in out
    )


def test_client_server_rejection(env, rendezqueue_server):
    url = rendezqueue_server
    lobby_key = f"test_game_{int(time.time())}"

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
    )

    try:
        assert server_proc.stdout is not None
        read_until(server_proc.stdout, "Server is live")

        x_key = f"{lobby_key}_X"

        # Send an invalid move to the server. The client should forward it (no local validation)
        # The server will reject it, and the client should print the rejection and exit 1
        x_res = subprocess.run(
            [
                sys.executable,
                CLIENT_PY,
                "--rendezqueue_api_url",
                url,
                "--key",
                x_key,
                "--move",
                "invalid_move_123",
            ],
            env=env,
            capture_output=True,
            text=True,
            timeout=10,
        )

        # Test client.py no local move validation & Server rejection detection
        assert x_res.returncode == 1
        assert "Server rejected the move. It is still your turn." in x_res.stdout

    finally:
        server_proc.terminate()
        server_proc.wait()


def test_server_log_sxpb_old_maid(env, rendezqueue_server, tmp_path):
    url = rendezqueue_server
    lobby_key = f"test_game_{int(time.time())}"
    history_file = tmp_path / "hist.sxpb"

    players_sxpb = """
    (()) 
    (() (premoves (()) "H4 S4 D5 C5 HQ")) 
    (() (premoves (()) "0? Are you hiding the Old Maid?" "0! I take it!")) 
    (() (premoves (()) "Maybe!"))
    """

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
            "old_maid",
            "--players",
            players_sxpb,
            "--log_sxpb",
            str(history_file),
            "--turn_limit",
            "4",
        ],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    try:
        out, err = server_proc.communicate(timeout=15)
    except subprocess.TimeoutExpired:
        server_proc.terminate()
        out, err = server_proc.communicate()

    assert history_file.exists(), (
        f"History file was not created. Server Output:\n{out}\n{err}"
    )
    content = history_file.read_text()

    assert "(())" in content
    assert '(turn (p 0) (txt "H4 S4 D5 C5 HQ"))' in content
    assert '(turn (p 1) (txt "0? Are you hiding the Old Maid?"))' in content
    assert '(turn (p 2) (txt "Maybe!"))' in content
    assert '(turn (p 1) (txt "0! I take it!"))' in content


def test_client_full_prompt_on_status_shows_full_prompt(
    env, rendezqueue_server, tmp_path
):
    """When --client_full_prompt_on is set, client --status shows the full LLM prompt."""
    url = rendezqueue_server
    lobby_key = f"test_game_{int(time.time())}"

    # X is external (client connects), O is LLM with a premove so the game doesn't hang
    players_file = tmp_path / "players.sxpb"
    players_file.write_text(
        "(())\n"
        '(() (name "Alice"))\n'
        '(() (model "empty-response-model") (premoves (()) "b2"))\n'
    )

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
            "--players",
            str(players_file),
            "--client_full_prompt_on",
        ],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    try:
        assert server_proc.stdout is not None
        read_until(server_proc.stdout, "Server is live")

        x_key = f"{lobby_key}_X"

        # Client connects with --status. Should receive full prompt.
        x_res = subprocess.run(
            [
                sys.executable,
                CLIENT_PY,
                "--rendezqueue_api_url",
                url,
                "--key",
                x_key,
                "--status",
            ],
            env=env,
            capture_output=True,
            text=True,
            timeout=15,
        )

        assert x_res.returncode == 0, f"Client failed: {x_res.stderr}"
        assert "playing agent" in x_res.stdout, (
            f"Client prompt did not contain 'playing agent'.\nSTDOUT:\n{x_res.stdout}\nSTDERR:\n{x_res.stderr}"
        )
        assert "tictactoe" in x_res.stdout.lower() or "Tic-Tac-Toe" in x_res.stdout, (
            f"Client prompt did not reference tic-tac-toe.\nSTDOUT:\n{x_res.stdout}"
        )

    finally:
        server_proc.terminate()
        server_proc.wait()


def test_client_full_prompt_on_move_shows_full_prompt(
    env, rendezqueue_server, tmp_path
):
    """When --client_full_prompt_on is set, client --move shows the full prompt after move is accepted."""
    url = rendezqueue_server
    lobby_key = f"test_game_{int(time.time())}"

    # X is external (client connects and moves), O is LLM with premoves
    players_file = tmp_path / "players.sxpb"
    players_file.write_text(
        "(())\n"
        '(() (name "Alice"))\n'
        '(() (model "empty-response-model") (premoves (()) "b2" "c3"))\n'
    )

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
            "--players",
            str(players_file),
            "--client_full_prompt_on",
        ],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    try:
        assert server_proc.stdout is not None
        read_until(server_proc.stdout, "Server is live")

        x_key = f"{lobby_key}_X"

        # Client sends a valid move. After move is accepted, should get updated state with full prompt.
        x_res = subprocess.run(
            [
                sys.executable,
                CLIENT_PY,
                "--rendezqueue_api_url",
                url,
                "--key",
                x_key,
                "--move",
                "a1",
            ],
            env=env,
            capture_output=True,
            text=True,
            timeout=15,
        )

        assert x_res.returncode == 0, f"Client failed: {x_res.stderr}"
        assert "playing agent" in x_res.stdout, (
            f"Client prompt did not contain 'playing agent'.\nSTDOUT:\n{x_res.stdout}\nSTDERR:\n{x_res.stderr}"
        )

    finally:
        server_proc.terminate()
        server_proc.wait()


def test_client_full_prompt_on_game_over_skips_full_prompt(
    env, rendezqueue_server, tmp_path
):
    """When --client_full_prompt_on is set, client suppresses full prompt on game over."""
    url = rendezqueue_server
    lobby_key = f"test_game_{int(time.time())}"

    # X is external with premoves to win, O is LLM with premoves.
    # X wins: a1, b1, c1 (vertical column) — O plays a2, b2.
    players_file = tmp_path / "players.sxpb"
    players_file.write_text(
        "(())\n"
        '(() (name "Alice") (premoves (()) "a1" "b1" "c1"))\n'
        '(() (model "empty-response-model") (premoves (()) "a2" "b2"))\n'
    )

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
            "--players",
            str(players_file),
            "--client_full_prompt_on",
        ],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    try:
        assert server_proc.stdout is not None
        read_until(server_proc.stdout, "Game concluded")

        x_key = f"{lobby_key}_X"

        # Client connects after premoves have resolved the game.
        # The client will see either the current board or GAME_OVER state.
        # On GAME_OVER, it should NOT include the full prompt.
        x_res = subprocess.run(
            [
                sys.executable,
                CLIENT_PY,
                "--rendezqueue_api_url",
                url,
                "--key",
                x_key,
                "--status",
            ],
            env=env,
            capture_output=True,
            text=True,
            timeout=15,
        )

        assert "Final Board:" in x_res.stdout
        assert "Game Over! Winner: X" in x_res.stdout
        assert "playing agent" not in x_res.stdout, (
            f"Client prompt incorrectly contained 'playing agent' on game over.\nSTDOUT:\n{x_res.stdout}"
        )

    finally:
        server_proc.terminate()
        server_proc.wait()


def test_client_full_prompt_on_sxpb_move_parsing(env, rendezqueue_server, tmp_path):
    """When --client_full_prompt_on is set, client moves are parsed as SxPB (answer field)."""
    url = rendezqueue_server
    lobby_key = f"test_game_{int(time.time())}"

    # X is external, O is LLM with premove
    players_file = tmp_path / "players.sxpb"
    players_file.write_text(
        "(())\n"
        '(() (name "Alice"))\n'
        '(() (model "empty-response-model") (premoves (()) "b2"))\n'
    )

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
            "--players",
            str(players_file),
            "--client_full_prompt_on",
        ],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    try:
        assert server_proc.stdout is not None
        read_until(server_proc.stdout, "Server is live")

        x_key = f"{lobby_key}_X"

        # Send move as SxPB (answer "a1") — server should parse the answer field.
        x_res = subprocess.run(
            [
                sys.executable,
                CLIENT_PY,
                "--rendezqueue_api_url",
                url,
                "--key",
                x_key,
                "--move",
                '(answer "a1")',
            ],
            env=env,
            capture_output=True,
            text=True,
            timeout=15,
        )

        assert x_res.returncode == 0, f"Client failed: {x_res.stderr}"
        # Move should be accepted — the board should show X at a1.
        assert "X" in x_res.stdout or "a1" in x_res.stdout.lower(), (
            f"Move not reflected in output.\nSTDOUT:\n{x_res.stdout}\nSTDERR:\n{x_res.stderr}"
        )
        # Prompt should tell the client to use --move with SxPB.
        assert "--move" in x_res.stdout, (
            f"Prompt did not mention --move flag.\nSTDOUT:\n{x_res.stdout}"
        )

    finally:
        server_proc.terminate()
        server_proc.wait()
