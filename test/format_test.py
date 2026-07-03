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
from sxpb_game.by_title.resistance.logic import ResistanceLogic
from sxpb_game.by_title.chameleon.logic import ChameleonLogic
from sxpb_game.by_title.twenty_questions.logic import TwentyQuestionsLogic
from sxpb_game.by_title.codenames.logic import CodenamesLogic
from sxpb_game.by_title.telephone.logic import TelephoneLogic
from sxpb_game.by_title.cthulhu.logic import CthulhuLogic
from sxpb_game.by_title.old_maid.logic import OldMaidLogic
from sxpb_game.by_title.skull.logic import SkullLogic
from sxpb_game.by_title.battleship.logic import BattleshipLogic


def get_all_game_titles() -> list[str]:
    base_dir = os.path.join(
        os.path.dirname(__file__), "..", "src", "sxpb_game", "by_title"
    )
    titles = []
    for entry in os.listdir(base_dir):
        if os.path.isdir(os.path.join(base_dir, entry)) and entry != "__pycache__":
            titles.append(entry)
    return sorted(titles)


def get_all_example_titles() -> list[str]:
    base_dir = os.path.join(os.path.dirname(__file__), "..", "example", "view_by_title")
    if not os.path.exists(base_dir):
        return []
    titles = []
    for entry in os.listdir(base_dir):
        if os.path.isdir(os.path.join(base_dir, entry)):
            titles.append(entry)
    return sorted(titles)


def test_directory_consistency() -> None:
    logic_titles = set(get_all_game_titles())
    example_titles = set(get_all_example_titles())

    missing_examples = logic_titles - example_titles
    extra_examples = example_titles - logic_titles

    msg = ""
    if missing_examples:
        msg += f"Logic titles missing example directories: {sorted(list(missing_examples))}\n"
    if extra_examples:
        msg += f"Example directories with no corresponding logic: {sorted(list(extra_examples))}\n"

    if msg:
        assert False, msg


@pytest.mark.parametrize("game_title", get_all_game_titles())
def test_game_format(game_title: str) -> None:
    example_dir = os.path.join(
        os.path.dirname(__file__), "..", "example", "view_by_title", game_title
    )
    history_sxpb_path = os.path.join(example_dir, "history.sxpb")
    state_sxpb_path = os.path.join(example_dir, "state.sxpb")
    players_sxpb_path = os.path.join(example_dir, "players.sxpb")

    if not os.path.exists(state_sxpb_path) or not os.path.exists(players_sxpb_path):
        # We handle the error here in case test_directory_consistency didn't fail first
        pytest.skip(f"Example files missing for {game_title}")

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
    elif game_title == "resistance":
        game = ResistanceLogic(num_players=6)
        test_player_idx = 1
    elif game_title == "chameleon":
        game = ChameleonLogic(num_players=6)
        test_player_idx = 1
    elif game_title == "twenty_questions":
        game = TwentyQuestionsLogic()
        test_player_idx = 1
    elif game_title == "codenames":
        # Need deterministic words for the test
        import unittest.mock

        with (
            unittest.mock.patch("random.sample") as mock_sample,
            unittest.mock.patch("random.shuffle"),
        ):
            words = [
                "APPLE",
                "BANANA",
                "CHERRY",
                "DOG",
                "ELEPHANT",
                "FROG",
                "GRAPE",
                "HOUSE",
                "ICE",
                "JACKET",
                "KITE",
                "LEMON",
                "MOUSE",
                "NIGHT",
                "ORANGE",
                "PIANO",
                "QUEEN",
                "RIVER",
                "SNAKE",
                "TIGER",
                "UMBRELLA",
                "VIOLIN",
                "WHALE",
                "XYLOPHONE",
                "YACHT",
            ]
            mock_sample.return_value = words
            game = CodenamesLogic()
        test_player_idx = 1
    elif game_title == "telephone":
        game = TelephoneLogic(num_players=3)
        test_player_idx = 0
    elif game_title == "cthulhu":
        game = CthulhuLogic(num_players=5)
        test_player_idx = 1
    elif game_title == "old_maid":
        game = OldMaidLogic()
        test_player_idx = 1
    elif game_title == "skull":
        game = SkullLogic(num_players=4)
        test_player_idx = 1
    elif game_title == "battleship":
        game = BattleshipLogic()
        test_player_idx = 0
    else:
        assert False, (
            f"Unknown game {game_title} - logic not imported in format_test.py"
        )

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

    if generated_state.strip() != expected_state.strip():
        assert False, (
            f"State mismatch for {game_title}.\nExpected:\n{expected_state}\n\nGot:\n{generated_state}"
        )

    if generated_history.strip() != expected_history.strip():
        assert False, (
            f"History mismatch for {game_title}.\nExpected:\n{expected_history}\n\nGot:\n{generated_history}"
        )


def test_snapshot_catches_formatting_drift() -> None:
    """Prove that the exact comparison catches formatting changes.

    Deliberately corrupt the tictactoe snapshot with an extra space indent
    and verify the comparison detects it. This guards against the
    whitespace-washing bug that silently disabled snapshot comparison for
    over 3 months.
    """
    example_dir = os.path.join(
        os.path.dirname(__file__), "..", "example", "view_by_title", "tictactoe"
    )
    state_sxpb_path = os.path.join(example_dir, "state.sxpb")
    players_sxpb_path = os.path.join(example_dir, "players.sxpb")

    with open(state_sxpb_path, "r") as f:
        expected_state = f.read().strip()

    with open(players_sxpb_path, "r") as f:
        premoves_data = cast(list[dict[str, Any]], sxpb.loads(f.read()))

    game = TicTacToeLogic()
    while not game.is_game_over():
        curr = game.get_current_player()
        if curr is None or not premoves_data[curr].get("premoves"):
            break
        move = premoves_data[curr]["premoves"].pop(0)
        game.make_move(curr, move)

    generated_state = game.render_player_view(0).strip()

    # Sanity: real snapshot matches real output.
    assert generated_state == expected_state, (
        "Snapshot is out of date — regenerate it before running this test."
    )

    # Corrupt: insert an extra space on the first row line after (board.
    corrupted = expected_state.replace("\n (row3", "\n  (row3", 1)
    assert corrupted != expected_state, "Corruption had no effect"
    assert generated_state != corrupted, (
        "Comparison FAILED to detect formatting drift!\n"
        "An extra space indent should cause a mismatch."
    )
