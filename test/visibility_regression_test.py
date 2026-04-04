import os
import sys

# Ensure we can import from src
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

from game_eval.logic import GameLogic
from sxpb_game.by_title.tictactoe.logic import TicTacToeLogic
from sxpb_game.by_title.mafia.logic import MafiaLogic


def test_base_logic_visibility_is_empty():
    """Verify that GameLogic defaults to an empty list to protect player anonymity."""

    class GenericGame(GameLogic):
        def get_player_identifiers(self):
            return ["P1", "P2"]

    game = GenericGame()
    assert game.get_visible_players(0) == [], (
        "Base GameLogic should return an empty list for visibility!"
    )


def test_tictactoe_visibility_is_empty():
    """Verify that Tic-Tac-Toe specifically maintains player anonymity."""
    game = TicTacToeLogic()
    assert game.get_visible_players(0) == [], (
        "Tic-Tac-Toe should not leak player identities!"
    )


def test_mafia_visibility_is_populated():
    """Verify that games that *want* visible identities still have them."""
    game = MafiaLogic(num_players=3)
    visible = game.get_visible_players(1)
    assert 1 in visible and 2 in visible and 3 in visible
    assert 0 not in visible, "GM should remain hidden in Mafia"


if __name__ == "__main__":
    try:
        test_base_logic_visibility_is_empty()
        print("PASS: Base logic visibility is empty.")
        test_tictactoe_visibility_is_empty()
        print("PASS: Tic-Tac-Toe visibility is empty.")
        test_mafia_visibility_is_populated()
        print("PASS: Mafia visibility is correctly overridden.")
    except AssertionError as e:
        print(f"FAIL: {e}")
        sys.exit(1)
