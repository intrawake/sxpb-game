import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))
from sxpb_game.by_title.skull.logic import SkullLogic


def test_skull_full_game_random():
    """Run a full game with random algorithms to ensure no crashes."""
    logic = SkullLogic(num_players=4)

    max_moves = 1000
    move_count = 0

    while not logic.is_game_over() and move_count < max_moves:
        curr_p = logic.get_current_player()
        assert curr_p is not None

        move, err = logic.get_algorithm_move(curr_p, "random")
        assert err is None
        assert move is not None

        res = logic.make_move(curr_p, move)
        assert res.success, f"Move failed: {move} - {res.reason} (phase: {logic.phase})"

        # Test rendering view and history does not crash
        logic.render_player_view(curr_p)
        logic.render_player_history(curr_p)

        move_count += 1

    assert logic.is_game_over(), "Game did not finish within 1000 moves."
    assert logic._winner is not None


def test_skull_basic_flow():
    logic = SkullLogic(num_players=3)

    assert logic.phase == "FIRST_DISC"

    # All 3 play their first disc
    assert logic.make_move(1, "play rose").success
    assert logic.make_move(2, "play skull").success
    assert logic.make_move(3, "play rose").success

    assert logic.phase == "PLAY_OR_BID"

    # p1 bids
    assert logic.make_move(1, "bid 1").success
    assert logic.phase == "BIDDING"

    # p2 passes
    assert logic.make_move(2, "pass").success
    # p3 bids 2
    assert logic.make_move(3, "bid 2").success
    # p1 passes
    assert logic.make_move(1, "pass").success

    assert logic.phase == "CHALLENGE_FLIP"
    assert logic.highest_bidder == 2
    assert logic.highest_bid == 2
    assert logic.current_player == 2

    # p3 flips p1's stack (p2's own stack was flipped automatically)
    assert logic.make_move(3, "flip p1").success

    # Challenge won, score = 1
    assert logic.players[2]["score"] == 1
    assert logic.phase == "FIRST_DISC"
    assert logic.current_player == 2  # Winner starts next round


def test_skull_auto_flip_max_bid_fail():
    logic = SkullLogic(num_players=3)

    logic.make_move(1, "play rose")
    logic.make_move(2, "play skull")
    logic.make_move(3, "play rose")

    # P1 bids 3 (max bid, as there are 3 discs on table)
    res = logic.make_move(1, "bid 3")
    assert res.success

    # Should automatically flip P1's stack (rose), then P2's stack (skull)
    # Hitting P2's skull triggers random discard phase via GM
    assert logic.phase == "CHALLENGER_RANDOM_DISCARD"
    assert logic.skull_owner_idx == 1


def test_skull_auto_flip_max_bid_win():
    logic = SkullLogic(num_players=3)

    logic.make_move(1, "play rose")
    logic.make_move(2, "play rose")
    logic.make_move(3, "play rose")

    # P1 bids 3 (max bid)
    res = logic.make_move(1, "bid 3")
    assert res.success

    # Should automatically flip all 3 roses and win the round immediately
    assert logic.players[0]["score"] == 1
    assert logic.phase == "FIRST_DISC"
    assert logic.current_player == 0
