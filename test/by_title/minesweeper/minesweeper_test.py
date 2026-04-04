import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from sxpb_game.by_title.minesweeper.logic import MinesweeperLogic


def normalize_sxpb(text):
    lines = [line.strip() for line in text.strip().splitlines()]
    lines = [line for line in lines if line]
    return "\n".join(lines)


def test_minesweeper_example():
    example_file = os.path.join(
        os.path.dirname(__file__),
        "..",
        "..",
        "..",
        "example",
        "view_by_title",
        "minesweeper.sxpb",
    )

    with open(example_file, "r") as f:
        expected_sxpb = f.read().strip()

    # Secret is "a1 b2 c3 d4 e5 f6 g7 h8", passed to GM move.
    game = MinesweeperLogic(mine_input="a1 b2 c3 d4 e5 f6 g7 h8")

    # Turn 1: Player moves "Oa8"
    assert game.get_current_player() == 1
    assert game.make_move(1, "Oa8").success

    # Turn 2: GM sets mines
    assert game.get_current_player() == 0
    assert game.make_move(0, "a1 b2 c3 d4 e5 f6 g7 h8").success

    # Turn 3: Player moves "Fa1"
    assert game.get_current_player() == 1
    assert game.make_move(1, "Fa1").success

    # The original eval.py print-state uses player 1 view for final output
    generated_sxpb = game.render_player_view(1).strip()

    if normalize_sxpb(generated_sxpb) == normalize_sxpb(expected_sxpb):
        print("PASS: Minesweeper output matches expected.")
    else:
        print("FAIL: Minesweeper output mismatch")
        print("Expected:")
        print(expected_sxpb)
        print("Got:")
        print(generated_sxpb)
        sys.exit(1)


def test_minesweeper_multiple_moves():
    game = MinesweeperLogic(mine_input="h8 h7 b8 b1")

    # Turn 1: Player moves "Oa8"
    assert game.get_current_player() == 1
    assert game.make_move(1, "Oa8").success

    # Turn 2: GM sets mines
    assert game.get_current_player() == 0
    assert game.make_move(0, "h8 h7 b8 b1").success

    # Turn 3: Player chains moves
    assert game.get_current_player() == 1
    # Move should parse properly: reveal a1, flag h8, unflag h8
    assert game.make_move(1, "Oa1 Fh8 Uh8").success

    assert (0, 0) in game.revealed  # a1
    assert (7, 7) not in game.flags  # h8 (flagged then unflagged)
    assert not game.is_game_over()

    # Chain that ends in a mine hit
    assert game.make_move(1, "Ob2 Oh8 Oa2").success
    assert (1, 1) in game.revealed  # b2 was revealed
    assert (7, 7) in game.mines
    assert game.hit_mine
    assert game.is_game_over()
    # a2 should not be revealed because h8 hit a mine
    assert (0, 1) not in game.revealed
    print("PASS: Minesweeper multiple moves test.")


def test_minesweeper_multiple_moves_2():
    game = MinesweeperLogic(mine_input="a1 b2 c3 d4 e5 f6 g7 h8")
    assert game.get_current_player() == 1
    assert game.make_move(1, "Oh1").success  # First move

    assert game.get_current_player() == 0
    assert game.make_move(0, "a1 b2 c3 d4 e5 f6 g7 h8").success  # GM sets mines

    assert game.get_current_player() == 1
    # Multiple moves in one turn: Flag a1, Reveal b1, Reveal c1
    # a1 is (0,0), b1 is (1,0), c1 is (2,0)
    assert game.make_move(1, "Fa1 Ob1 Oc1").success

    assert (0, 0) in game.flags
    assert (1, 0) in game.revealed
    assert (2, 0) in game.revealed


if __name__ == "__main__":
    test_minesweeper_example()
    test_minesweeper_multiple_moves()
    print("All Minesweeper tests passed.")
    test_minesweeper_multiple_moves()
