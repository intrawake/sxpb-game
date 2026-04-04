import sys
import os
import pytest

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

import sxpb
from sxpb_game.by_title.tictactoe.logic import TicTacToeLogic
from sxpb_game.by_title.wordle.logic import WordleLogic
from sxpb_game.by_title.connect_four.logic import ConnectFourLogic
from sxpb_game.by_title.mastermind.logic import MastermindLogic
from sxpb_game.by_title.blackjack.logic import BlackjackLogic
from sxpb_game.by_title.minesweeper.logic import MinesweeperLogic
from sxpb_game.by_title.sudoku.logic import SudokuLogic
from sxpb_game.by_title.old_maid.logic import OldMaidLogic
from sxpb_game.by_title.cthulhu.logic import CthulhuLogic
from sxpb_game.by_title.codenames.logic import CodenamesLogic
from sxpb_game.by_title.trolley.logic import TrolleyLogic


def get_games():
    return [
        ("tictactoe", lambda: TicTacToeLogic()),
        ("wordle", lambda: WordleLogic("TRAIN")),
        ("connect_four", lambda: ConnectFourLogic()),
        ("mastermind", lambda: MastermindLogic("RGBY")),
        ("blackjack", lambda: BlackjackLogic()),
        ("minesweeper", lambda: MinesweeperLogic("a8 h8 a1")),
        ("sudoku", lambda: SudokuLogic("")),
        ("old_maid", lambda: OldMaidLogic()),
        ("cthulhu", lambda: CthulhuLogic(4)),
        ("codenames", lambda: CodenamesLogic()),
        ("trolley", lambda: TrolleyLogic()),
    ]


@pytest.mark.parametrize("name, game_factory", get_games())
def test_player_view_is_parsable_sxpb(name, game_factory):
    game = game_factory()
    players = game.get_player_identifiers()
    for idx in range(len(players)):
        view = game.render_player_view(idx)
        try:
            parsed = sxpb.loads(view)
            assert parsed is not None or view.strip() == ""
        except Exception as e:
            assert False, (
                f"Failed to parse player view for {name}, player {idx}. View:\n{view}\nError: {e}"
            )


@pytest.mark.parametrize("name, game_factory", get_games())
def test_player_history_is_parsable_sxpb(name, game_factory):
    game = game_factory()
    players = game.get_player_identifiers()
    for idx in range(len(players)):
        history = game.render_player_history(idx)
        if history and history.strip():
            try:
                parsed = sxpb.loads(history)
                assert parsed is not None
            except Exception as e:
                assert False, (
                    f"Failed to parse player history for {name}, player {idx}. History:\n{history}\nError: {e}"
                )
