import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from sxpb_game.by_title.mastermind.logic import MastermindLogic


def test_mastermind_example():
    example_file = os.path.join(
        os.path.dirname(__file__),
        "..",
        "..",
        "..",
        "example",
        "view_by_title",
        "mastermind.sxpb",
    )

    with open(example_file, "r") as f:
        expected_sxpb = f.read().strip()

    game = MastermindLogic(target_code="RGBY")

    guesses = ["BOBY", "GBOY", "POGR", "GPBY", "GRBY", "GGBY", "RGBY"]

    for guess in guesses:
        current_player_idx = game.get_current_player()
        assert current_player_idx is not None
        success = game.make_move(current_player_idx, guess)
        assert success, f"Move {guess} failed"

    generated_sxpb = game.render_player_view(1).strip()

    if generated_sxpb == expected_sxpb:
        print("PASS: Mastermind output matches expected.")
    else:
        print("FAIL: Mastermind output mismatch")
        print("Expected:")
        print(expected_sxpb)
        print("Got:")
        print(generated_sxpb)
        sys.exit(1)


if __name__ == "__main__":
    test_mastermind_example()
