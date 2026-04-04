import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from sxpb_game.by_title.tictactoe.logic import TicTacToeLogic


def normalize_sxpb(text):
    lines = [line.strip() for line in text.strip().splitlines()]
    lines = [line for line in lines if line]
    return "\n".join(lines)


def test_tictactoe_example():
    example_file = os.path.join(
        os.path.dirname(__file__),
        "..",
        "..",
        "..",
        "example",
        "view_by_title",
        "tictactoe.sxpb",
    )

    with open(example_file, "r") as f:
        expected_sxpb = f.read().strip()

    game = TicTacToeLogic()

    # Moves corresponding to example.sxpb: Xb2 Oa3 Xc1 Oa1 Xa2
    moves = ["b2", "a3", "c1", "a1", "a2"]

    for move in moves:
        current_player_idx = game.get_current_player()
        assert current_player_idx is not None
        success = game.make_move(current_player_idx, move)
        assert success, f"Move {move} failed"

    # In single-player or symmetric view, render player view. We can render player 0 view
    generated_view = game.render_player_view(0).strip()
    generated_history = game.render_player_history(0).strip()

    generated_sxpb = (
        f"{generated_view}\n\n{generated_history}"
        if generated_history
        else generated_view
    )

    if normalize_sxpb(generated_sxpb) == normalize_sxpb(expected_sxpb):
        print("PASS: TicTacToe output matches expected.")
    else:
        print("FAIL: TicTacToe output mismatch")
        print("Expected:")
        print(expected_sxpb)
        print("Got:")
        print(generated_sxpb)
        sys.exit(1)


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
    test_tictactoe_example()
    test_tictactoe_visibility()
