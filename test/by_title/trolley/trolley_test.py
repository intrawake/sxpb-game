import sys
import os

# Set up paths for the game engine and the game logic
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from sxpb_game.by_title.trolley.logic import TrolleyLogic


def test_trolley_game():
    game = TrolleyLogic()

    # p0: Setup Track A
    assert game.get_current_player() == 0
    success = game.make_move(0, "5 people")
    assert success
    assert game.track_a == "5 people"
    assert game.track_b is None

    # p0: Setup Track B
    assert game.get_current_player() == 0
    success = game.make_move(0, "1 person")
    assert success
    assert game.track_b == "1 person"

    # p2: Argument (Pull)
    assert game.get_current_player() == 1
    success = game.make_move(
        1, "Pulling the lever saves 4 lives. It is the utilitarian choice."
    )
    assert success

    # p3: Argument (Stay)
    assert game.get_current_player() == 2
    success = game.make_move(
        2, "Pulling the lever makes you an active killer. Inaction is not murder."
    )
    assert success

    # p1: Judge (Decision)
    assert game.get_current_player() == 3
    success = game.make_move(3, "pull")
    assert success
    assert game.judge_decision == "pull"
    assert game.is_game_over()
    assert game.winner == "p1"

    # Final View check
    view = game.render_player_view(0)
    assert '(track_a "5 people")' in view
    assert '(track_b "1 person")' in view
    assert '(decision "pull")' in view
    assert '(winner "p1")' in view

    # History check
    history = game.render_player_history(0)
    assert (
        '(p1 "Pulling the lever saves 4 lives. It is the utilitarian choice.")'
        in history
    )
    assert (
        '(p2 "Pulling the lever makes you an active killer. Inaction is not murder.")'
        in history
    )
    assert '(p3 "pull")' in history


def test_trolley_random_algorithm():
    game = TrolleyLogic()
    assert game.get_current_player() == 0

    # Ask for random move for Track A
    move1, error1 = game.get_algorithm_move(0, "random")
    assert error1 is None
    assert move1 is not None

    # Execute random move for Track A
    success1 = game.make_move(0, move1)
    assert success1
    assert game.get_current_player() == 0

    # Ask for random move for Track B
    move2, error2 = game.get_algorithm_move(0, "random")
    assert error2 is None
    assert move2 is not None

    # Execute random move for Track B
    success2 = game.make_move(0, move2)
    assert success2
    assert game.get_current_player() == 1


if __name__ == "__main__":
    test_trolley_game()
    test_trolley_random_algorithm()
    print("Trolley game tests passed!")
