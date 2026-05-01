import os
import subprocess
import sys
import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SERVER_PY = os.path.join(REPO_ROOT, "src", "sxpb_game", "harness", "sxpb_game_main.py")


@pytest.fixture
def base_env():
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{REPO_ROOT}:{os.path.join(REPO_ROOT, 'src')}"
    return env


def test_server_external_requires_rendezqueue_url(base_env):
    # Two human players, no LLMs, no URL
    players_sxpb = "(()) (())"
    cmd = [sys.executable, SERVER_PY, "--game", "tictactoe", "--players", players_sxpb]

    proc = subprocess.Popen(
        cmd,
        env=base_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        cwd=REPO_ROOT,
    )
    stdout, _ = proc.communicate(timeout=10)

    assert proc.returncode != 0
    assert "Error: --rendezqueue_api_url is required" in stdout
    assert "players ['X', 'O'] are expected to connect externally" in stdout


def test_server_local_automated_no_rendezqueue_url(base_env):
    # Two algorithms, no URL. Should start and run to completion (since they are random).
    players_sxpb = "(()) (() (algorithm random)) (() (algorithm random))"
    cmd = [sys.executable, SERVER_PY, "--game", "tictactoe", "--players", players_sxpb]

    proc = subprocess.Popen(
        cmd,
        env=base_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        cwd=REPO_ROOT,
    )
    stdout, _ = proc.communicate(timeout=10)

    assert proc.returncode == 0
    assert "(clientless)" in stdout
    assert "Game concluded" in stdout


def test_server_llm_requires_openai_url(base_env):
    # One LLM player, but we provide a dummy rendezqueue URL so it doesn't fail on that.
    # We want to check that it still requires --openai_api_url.
    players_sxpb = '(()) (() (model "fake-model"))'
    cmd = [
        sys.executable,
        SERVER_PY,
        "--game",
        "tictactoe",
        "--players",
        players_sxpb,
        "--rendezqueue_api_url",
        "http://unused",
    ]

    proc = subprocess.Popen(
        cmd,
        env=base_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        cwd=REPO_ROOT,
    )
    stdout, _ = proc.communicate(timeout=10)

    assert proc.returncode != 0
    assert "Error: Player X is an LLM, but --openai_api_url was not provided" in stdout
