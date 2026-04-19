import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from sxpb_game.by_title.tictactoe.logic import TicTacToeLogic


def normalize_sxpb(text):
    lines = [line.strip() for line in text.strip().splitlines()]
    lines = [line for line in lines if line]
    return "\n".join(lines)


def test_tictactoe_visibility():
    """Ensure Tic-Tac-Toe doesn't leak player metadata (regression test)."""
    game = TicTacToeLogic()
    # In Tic-Tac-Toe, players should not be visible to each other by default.
    visible = game.get_visible_players(0)
    if visible == []:
        print("PASS: Tic-Tac-Toe visibility is correctly empty (anonymized).")
    else:
        print(f"FAIL: Tic-Tac-Toe visibility leaked: {visible}")
        sys.exit(1)


if __name__ == "__main__":
    test_tictactoe_visibility()
