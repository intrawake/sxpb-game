import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from sxpb_game.by_title.connect_four.logic import ConnectFourLogic


def normalize_sxpb(text):
    lines = [line.strip() for line in text.strip().splitlines()]
    lines = [line for line in lines if line]
    return "\n".join(lines)


def test_connect_four_example():
    example_file = os.path.join(
        os.path.dirname(__file__),
        "..",
        "..",
        "..",
        "example",
        "view_by_title",
        "connect_four.sxpb",
    )

    with open(example_file, "r") as f:
        expected_sxpb = f.read().strip()

    game = ConnectFourLogic()

    guesses = ["c1", "d1", "d2", "e1", "e2", "f1", "g1", "b1", "f2", "c2", "g2"]

    for guess in guesses:
        current_player_idx = game.get_current_player()
        assert current_player_idx is not None
        success = game.make_move(current_player_idx, guess)
        assert success, f"Move {guess} failed"

    generated_view = game.render_player_view(0).strip()
    generated_history = game.render_player_history(0).strip()

    generated_sxpb = (
        f"{generated_view}\n\n{generated_history}"
        if generated_history
        else generated_view
    )

    if normalize_sxpb(generated_sxpb) == normalize_sxpb(expected_sxpb):
        print("PASS: Connect Four output matches expected.")
    else:
        print("FAIL: Connect Four output mismatch")
        print("Expected:")
        print(expected_sxpb)
        print("Got:")
        print(generated_sxpb)
        sys.exit(1)


if __name__ == "__main__":
    test_connect_four_example()
