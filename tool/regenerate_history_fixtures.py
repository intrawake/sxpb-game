"""Regenerate all example/view_by_title/<game>/history.sxpb fixtures.

Drives each game with the premoves from players.sxpb (same logic as
test/format_test.py), writes the new render_player_history output, and
fails loudly if state.sxpb changes.
"""

import os
import sys
from typing import Any, cast

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

EXAMPLE_ROOT = os.path.join(os.path.dirname(__file__), "..", "example", "view_by_title")

VIEWER_IDX = {
    "tictactoe": 0,
    "mafia": 0,
    "blackjack": 1,
    "connect_four": 0,
    "mastermind": 1,
    "sudoku": 1,
    "trolley": 3,
    "wordle": 1,
    "minesweeper": 1,
    "resistance": 1,
    "chameleon": 1,
    "twenty_questions": 1,
    "codenames": 1,
    "telephone": 0,
    "cthulhu": 1,
    "old_maid": 1,
    "skull": 1,
    "battleship": 0,
}


def make_game(game_title: str):
    if game_title == "tictactoe":
        return TicTacToeLogic()
    if game_title == "mafia":
        return MafiaLogic(num_players=6)
    if game_title == "blackjack":
        return BlackjackLogic()
    if game_title == "connect_four":
        return ConnectFourLogic()
    if game_title == "mastermind":
        return MastermindLogic()
    if game_title == "sudoku":
        return SudokuLogic()
    if game_title == "trolley":
        return TrolleyLogic()
    if game_title == "wordle":
        return WordleLogic()
    if game_title == "minesweeper":
        return MinesweeperLogic()
    if game_title == "resistance":
        return ResistanceLogic(num_players=6)
    if game_title == "chameleon":
        return ChameleonLogic(num_players=6)
    if game_title == "twenty_questions":
        return TwentyQuestionsLogic()
    if game_title == "codenames":
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
            return CodenamesLogic()
    if game_title == "telephone":
        return TelephoneLogic(num_players=3)
    if game_title == "cthulhu":
        return CthulhuLogic(num_players=5)
    if game_title == "old_maid":
        return OldMaidLogic()
    if game_title == "skull":
        return SkullLogic(num_players=4)
    if game_title == "battleship":
        return BattleshipLogic()
    raise AssertionError(f"Unknown game {game_title}")


def main() -> None:
    changed = []
    for game_title in sorted(os.listdir(EXAMPLE_ROOT)):
        example_dir = os.path.join(EXAMPLE_ROOT, game_title)
        if not os.path.isdir(example_dir):
            continue
        history_path = os.path.join(example_dir, "history.sxpb")
        state_path = os.path.join(example_dir, "state.sxpb")
        players_path = os.path.join(example_dir, "players.sxpb")
        if not (os.path.exists(state_path) and os.path.exists(players_path)):
            continue

        with open(state_path) as f:
            expected_state = f.read().strip()
        with open(players_path) as f:
            premoves_data = cast(list[dict[str, Any]], sxpb.loads(f.read()))

        game = make_game(game_title)
        while not game.is_game_over():
            curr = game.get_current_player()
            if curr is None:
                break
            if curr >= len(premoves_data) or not premoves_data[curr].get("premoves"):
                break
            move = premoves_data[curr]["premoves"].pop(0)
            result = game.make_move(curr, move)
            is_success = getattr(result, "success", bool(result))
            assert is_success, (
                f"Premove {move!r} failed for player {curr} in {game_title}"
            )

        generated_state = game.render_player_view(VIEWER_IDX[game_title]).strip()
        assert generated_state == expected_state, (
            f"STATE CHANGED for {game_title} — not writing history!"
        )
        generated_history = game.render_player_history(VIEWER_IDX[game_title]).strip()
        if os.path.exists(history_path):
            old = open(history_path).read().strip()
        else:
            old = ""
        if old != generated_history:
            with open(history_path, "w") as f:
                f.write(generated_history + "\n")
            changed.append(game_title)
    if changed:
        print("Regenerated:", ", ".join(changed))
    else:
        print("No history fixtures changed.")


if __name__ == "__main__":
    main()
