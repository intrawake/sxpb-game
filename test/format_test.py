import sys
import os
from typing import Any, cast
import pytest

# Ensure paths
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

import sxpb
from sxpb_game.by_title.tictactoe.logic import TicTacToeLogic
from sxpb_game.by_title.mafia.logic import MafiaLogic
from sxpb_game.by_title.blackjack.logic import BlackjackLogic
from sxpb_game.by_title.connect_four.logic import ConnectFourLogic
from sxpb_game.by_title.mastermind.logic import MastermindLogic
from sxpb_game.by_title.sudoku.logic import SudokuLogic
from sxpb_game.by_title.trolley.logic import TrolleyLogic
from sxpb_game.by_title.wordle.logic import WordleLogic
from sxpb_game.by_title.minesweeper.logic import MinesweeperLogic


def normalize_sxpb(text: str) -> str:
    lines = [line.strip() for line in text.strip().splitlines()]
    lines = [line for line in lines if line]
    return "\n".join(lines)


@pytest.mark.parametrize(
    "game_title",
    [
        "tictactoe",
        "mafia",
        "blackjack",
        "connect_four",
        "mastermind",
        "sudoku",
        "trolley",
        "wordle",
        "minesweeper",
    ],
)
def test_game_format(game_title: str) -> None:
    example_dir = os.path.join(
        os.path.dirname(__file__), "..", "example", "view_by_title", game_title
    )
    history_sxpb_path = os.path.join(example_dir, "history.sxpb")
    state_sxpb_path = os.path.join(example_dir, "state.sxpb")
    players_sxpb_path = os.path.join(example_dir, "players.sxpb")

    expected_history = ""
    if os.path.exists(history_sxpb_path):
        with open(history_sxpb_path, "r") as f:
            expected_history = f.read().strip()

    with open(state_sxpb_path, "r") as f:
        expected_state = f.read().strip()

    with open(players_sxpb_path, "r") as f:
        premoves_data = cast(list[dict[str, Any]], sxpb.loads(f.read()))

    test_player_idx = 0
    if game_title == "tictactoe":
        game = TicTacToeLogic()
    elif game_title == "mafia":
        game = MafiaLogic(num_players=6)
    elif game_title == "blackjack":
        game = BlackjackLogic()
        test_player_idx = 1
    elif game_title == "connect_four":
        game = ConnectFourLogic()
    elif game_title == "mastermind":
        game = MastermindLogic()
        test_player_idx = 1
    elif game_title == "sudoku":
        game = SudokuLogic()
        test_player_idx = 1
    elif game_title == "trolley":
        game = TrolleyLogic()
        test_player_idx = 3
    elif game_title == "wordle":
        game = WordleLogic()
        test_player_idx = 1
    elif game_title == "minesweeper":
        game = MinesweeperLogic()
        test_player_idx = 1
    else:
        assert False, f"Unknown game {game_title}"

    # We apply the premoves by repeatedly popping from the current player's list
    # until either the game ends or all premoves are exhausted.
    while not game.is_game_over():
        curr_player = game.get_current_player()
        if curr_player is None:
            break

        if curr_player >= len(premoves_data) or not premoves_data[curr_player].get(
            "premoves"
        ):
            break  # No more premoves for this player

        move = premoves_data[curr_player]["premoves"].pop(0)
        result = game.make_move(curr_player, move)
        is_success = result.success if hasattr(result, "success") else bool(result)
        assert is_success, f"Premove {move} failed for player {curr_player}"

    # Verify that all premoves were used
    for idx, p_data in enumerate(premoves_data):
        assert not p_data.get("premoves"), (
            f"Unused premoves for player {idx}: {p_data['premoves']}"
        )

    # Validate output
    generated_state = game.render_player_view(test_player_idx).strip()
    generated_history = game.render_player_history(test_player_idx).strip()

    if normalize_sxpb(generated_state) != normalize_sxpb(expected_state):
        assert False, (
            f"State mismatch for {game_title}.\nExpected:\n{expected_state}\n\nGot:\n{generated_state}"
        )

    if normalize_sxpb(generated_history) != normalize_sxpb(expected_history):
        assert False, (
            f"History mismatch for {game_title}.\nExpected:\n{expected_history}\n\nGot:\n{generated_history}"
        )
