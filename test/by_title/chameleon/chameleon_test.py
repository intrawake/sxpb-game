import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))
from sxpb_game.by_title.chameleon.logic import ChameleonLogic


def test_chameleon_full_game_random():
    """Run a full game with random algorithms to ensure no crashes."""
    logic = ChameleonLogic(num_players=6)

    # 1. SETUP_WORDS
    assert logic.get_current_player() == 0
    assert logic.phase == "SETUP_WORDS"
    move, _ = logic.get_algorithm_move(0, "random")
    assert move is not None
    assert logic.make_move(0, move).success

    # 2. SETUP_SECRET
    assert logic.get_current_player() == 0
    assert logic.phase == "SETUP_SECRET"
    move, _ = logic.get_algorithm_move(0, "random")
    assert move is not None
    assert logic.make_move(0, move).success

    # 3. SETUP_LEADER
    assert logic.get_current_player() == 0
    assert logic.phase == "SETUP_LEADER"
    move, _ = logic.get_algorithm_move(0, "random")
    assert move is not None
    assert logic.make_move(0, move).success
    leader_idx = logic.leader_idx
    assert leader_idx is not None

    # 4. SETUP_CHAMELEON
    assert logic.get_current_player() == 0
    assert logic.phase == "SETUP_CHAMELEON"
    move, _ = logic.get_algorithm_move(0, "random")
    assert move is not None
    assert logic.make_move(0, move).success
    cham_idx = logic.chameleon_idx
    assert cham_idx is not None

    assert leader_idx != cham_idx

    # 5. PLAYER_ORDER
    assert logic.get_current_player() == 0
    assert logic.phase == "PLAYER_ORDER"
    move, _ = logic.get_algorithm_move(0, "random")
    assert move is not None
    assert logic.make_move(0, move).success

    # 6. PLAYER_WORDS
    # Now all players say a word (leader first, by the random algorithm)
    for _ in range(logic.num_players):
        assert logic.phase == "PLAYER_WORDS"
        curr_p = logic.get_current_player()
        assert curr_p is not None
        move, _ = logic.get_algorithm_move(0 if curr_p is None else curr_p, "random")
        assert move is not None
        assert logic.make_move(
            0 if curr_p is None else curr_p, move if move is not None else ""
        )[0]

    # 7. DAY_ORDER
    assert logic.get_current_player() == 0
    assert logic.phase == "DAY_ORDER"
    move, _ = logic.get_algorithm_move(0, "random")
    assert move is not None
    assert logic.make_move(0, move).success

    # 8. DAY_DISCUSSION
    # 5 players -> 5 turns
    for _ in range(5):
        curr_p = logic.get_current_player()
        assert curr_p is not None
        # Just say something instead of asking a question for simple test
        assert logic.make_move(curr_p, "I am innocent.").success

    # 9. DAY_ORDER (Round 2)
    assert logic.get_current_player() == 0
    assert logic.phase == "DAY_ORDER"
    move, _ = logic.get_algorithm_move(0, "random")
    assert move is not None
    assert logic.make_move(0, move).success

    # 10. DAY_DISCUSSION
    for _ in range(5):
        curr_p = logic.get_current_player()
        assert curr_p is not None
        assert logic.make_move(curr_p, "I am innocent.").success

    # 11. VOTE_ORDER
    assert logic.get_current_player() == 0
    assert logic.phase == "VOTE_ORDER"
    move, _ = logic.get_algorithm_move(0, "random")
    assert move is not None
    assert logic.make_move(0, move).success

    # 12. DAY_VOTE
    # 4 voters (everyone but leader)
    for _ in range(4):
        assert logic.phase == "DAY_VOTE"
        curr_p = logic.get_current_player()
        assert curr_p is not None
        assert curr_p != leader_idx + 1
        move, _ = logic.get_algorithm_move(0 if curr_p is None else curr_p, "random")
        assert move is not None
        assert logic.make_move(
            0 if curr_p is None else curr_p, move if move is not None else ""
        ).success

    # Check if we go to tie break, or guess, or game over
    if logic.phase == "TIE_BREAK":
        curr_p = logic.get_current_player()
        assert curr_p is not None
        assert curr_p == leader_idx + 1
        move, _ = logic.get_algorithm_move(0 if curr_p is None else curr_p, "random")
        assert move is not None
        assert logic.make_move(
            0 if curr_p is None else curr_p, move if move is not None else ""
        ).success

    if logic.phase == "CHAMELEON_GUESS":
        curr_p = logic.get_current_player()
        assert curr_p is not None
        assert curr_p == cham_idx + 1
        move, _ = logic.get_algorithm_move(0 if curr_p is None else curr_p, "random")
        assert move is not None
        assert logic.make_move(
            0 if curr_p is None else curr_p, move if move is not None else ""
        ).success

    assert logic.is_game_over()
    assert logic.winner in ["Chameleon", "Players"]
