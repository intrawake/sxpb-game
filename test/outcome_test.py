"""Tests for get_player_outcomes() across game types."""

import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))
from sxpb_game.eval.logic import Outcome
from sxpb_game.by_title.tictactoe.logic import TicTacToeLogic
from sxpb_game.by_title.mafia.logic import MafiaLogic
from sxpb_game.by_title.resistance.logic import ResistanceLogic
from sxpb_game.by_title.chameleon.logic import ChameleonLogic
from sxpb_game.by_title.connect_four.logic import ConnectFourLogic


def _check(desc: str, outcomes, expected: dict[int, Outcome]):
    assert outcomes == expected, f"{desc}: got {outcomes!r}, expected {expected!r}"
    print(f"  PASS: {desc}")


def test_default_single_winner():
    """Default: single winner → WIN, others → LOSS."""
    g = TicTacToeLogic()
    # X wins top row
    g.board = {
        (0, 0): "X",
        (1, 0): "X",
        (2, 0): "X",
        (0, 1): " ",
        (1, 1): " ",
        (2, 1): " ",
        (0, 2): " ",
        (1, 2): " ",
        (2, 2): " ",
    }
    g.winner = "X"
    g.move_count = 5
    _check(
        "default single winner",
        g.get_player_outcomes(),
        {0: Outcome.WIN, 1: Outcome.LOSS},
    )


def test_default_draw():
    """Default: Draw → all DRAW."""
    g = TicTacToeLogic()
    g.winner = "Draw"
    g.move_count = 9
    _check("default draw", g.get_player_outcomes(), {0: Outcome.DRAW, 1: Outcome.DRAW})


def test_default_no_winner():
    """Default: no winner set → empty dict."""
    g = TicTacToeLogic()
    _check("default no winner", g.get_player_outcomes(), {})


def test_tictactoe_x_wins():
    """TicTacToe: X wins via played moves."""
    g = TicTacToeLogic()
    # X: a1, O: b1, X: a2, O: b2, X: a3
    for move in ["a1", "b1", "a2", "b2", "a3"]:
        p = g.get_current_player()
        assert p is not None
        assert g.make_move(p, move).success
    assert g.winner == "X"
    _check(
        "tictactoe X wins", g.get_player_outcomes(), {0: Outcome.WIN, 1: Outcome.LOSS}
    )


def test_tictactoe_o_wins():
    """TicTacToe: O wins via played moves."""
    g = TicTacToeLogic()
    # X: a1, O: b1, X: a2, O: b2, X: c1, O: b3
    for move in ["a1", "b1", "a2", "b2", "c1", "b3"]:
        p = g.get_current_player()
        assert p is not None
        assert g.make_move(p, move).success
    assert g.winner == "O"
    _check(
        "tictactoe O wins", g.get_player_outcomes(), {0: Outcome.LOSS, 1: Outcome.WIN}
    )


def test_tictactoe_draw():
    """TicTacToe: full-board draw."""
    g = TicTacToeLogic()
    for move in ["b2", "a1", "a3", "c1", "b1", "b3", "a2", "c2", "c3"]:
        p = g.get_current_player()
        assert p is not None
        assert g.make_move(p, move).success
    assert g.winner == "Draw"
    _check(
        "tictactoe draw", g.get_player_outcomes(), {0: Outcome.DRAW, 1: Outcome.DRAW}
    )


def test_connect_four_r_wins():
    """Connect Four: R wins → R gets WIN, Y gets LOSS."""
    g = ConnectFourLogic()
    for col in ["a", "e", "a", "e", "a", "e", "a"]:
        p = g.get_current_player()
        assert p is not None
        assert g.make_move(p, col).success
    assert g.winner == "R"
    _check(
        "connect_four R wins",
        g.get_player_outcomes(),
        {0: Outcome.WIN, 1: Outcome.LOSS},
    )


def test_mafia_team_win():
    """Mafia: Mafia team wins → Mafia WIN, Villagers LOSS."""
    g = MafiaLogic(num_players=6)  # 5 real players + GM
    g.make_move(0, "Mafia Mafia Villager Villager Villager")
    g.game_over = True
    g.result = "Mafia"
    _check(
        "mafia wins",
        g.get_player_outcomes(),
        {
            1: Outcome.WIN,
            2: Outcome.WIN,
            3: Outcome.LOSS,
            4: Outcome.LOSS,
            5: Outcome.LOSS,
        },
    )


def test_mafia_villager_win():
    """Mafia: Villagers win → Villagers WIN, Mafia LOSS."""
    g = MafiaLogic(num_players=6)
    g.make_move(0, "Mafia Mafia Villager Villager Villager")
    g.game_over = True
    g.result = "Villagers"
    _check(
        "villagers win",
        g.get_player_outcomes(),
        {
            1: Outcome.LOSS,
            2: Outcome.LOSS,
            3: Outcome.WIN,
            4: Outcome.WIN,
            5: Outcome.WIN,
        },
    )


def test_mafia_not_over():
    """Mafia: game not over → empty dict."""
    g = MafiaLogic(num_players=6)
    g.make_move(0, "Mafia Mafia Villager Villager Villager")
    _check("mafia not over", g.get_player_outcomes(), {})


def test_resistance_spy_win():
    """Resistance: Spy team wins → Spies WIN, Resistance LOSS."""
    g = ResistanceLogic(num_players=6)  # 5 real + GM
    g.teams = ["Spy", "Resistance", "Spy", "Resistance", "Resistance"]
    g.game_over = True
    g.result = "Spy"
    _check(
        "resistance spy win",
        g.get_player_outcomes(),
        {
            0: Outcome.WIN,
            1: Outcome.LOSS,
            2: Outcome.WIN,
            3: Outcome.LOSS,
            4: Outcome.LOSS,
        },
    )


def test_resistance_resistance_win():
    """Resistance: Resistance team wins."""
    g = ResistanceLogic(num_players=6)
    g.teams = ["Spy", "Resistance", "Spy", "Resistance", "Resistance"]
    g.game_over = True
    g.result = "Resistance"
    _check(
        "resistance resistance win",
        g.get_player_outcomes(),
        {
            0: Outcome.LOSS,
            1: Outcome.WIN,
            2: Outcome.LOSS,
            3: Outcome.WIN,
            4: Outcome.WIN,
        },
    )


def test_chameleon_chameleon_win():
    """Chameleon: Chameleon wins → chameleon WIN, players LOSS."""
    g = ChameleonLogic(num_players=5)  # 4 real + GM
    g.chameleon_idx = 2  # player 3 is chameleon
    g.game_over = True
    g.result = "Chameleon"
    _check(
        "chameleon win",
        g.get_player_outcomes(),
        {1: Outcome.LOSS, 2: Outcome.LOSS, 3: Outcome.WIN, 4: Outcome.LOSS},
    )


def test_chameleon_players_win():
    """Chameleon: Players win → chameleon LOSS, players WIN."""
    g = ChameleonLogic(num_players=5)
    g.chameleon_idx = 2
    g.game_over = True
    g.result = "Players"
    _check(
        "players win",
        g.get_player_outcomes(),
        {1: Outcome.WIN, 2: Outcome.WIN, 3: Outcome.LOSS, 4: Outcome.WIN},
    )


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
            except AssertionError as e:
                print(f"FAIL: {name}: {e}")
                failures += 1
            except Exception as e:
                print(f"ERROR: {name}: {e}")
                failures += 1
    print(f"\n{failures} failure(s)")
    sys.exit(1 if failures else 0)
