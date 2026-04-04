import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from sxpb_game.by_title.wordle.logic import WordleLogic


def test_wordle_win_on_last_move():
    """
    Regression test: Ensure Player 1 (Codebreaker) wins if they guess the
    correct word on their 6th and final attempt.
    """
    secret = "APPLE"
    game = WordleLogic(target_word=secret)

    # Moves 1-5: Incorrect guesses
    wrong_guesses = ["CHAIR", "TABLE", "FRUIT", "GRAPE", "BEACH"]
    for guess in wrong_guesses:
        assert game.make_move(1, guess).success
        assert not game.is_game_over()
        assert game.winner is None

    # Move 6: Correct guess
    assert game.make_move(1, secret).success
    assert game.is_game_over()

    # The winner should be Player 1 (the Codebreaker), not Player 0 (the Codemaker)
    assert game.winner == "1", f"Expected winner '1', got '{game.winner}'"


if __name__ == "__main__":
    try:
        test_wordle_win_on_last_move()
        print("PASS: Wordle last-move win test.")
    except AssertionError as e:
        print(f"FAIL: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)
