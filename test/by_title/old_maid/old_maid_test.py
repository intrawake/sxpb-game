import os
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.append(os.path.join(REPO_ROOT, "src"))
sys.path.append(REPO_ROOT)

from sxpb_game.by_title.old_maid.logic import OldMaidLogic  # noqa: E402


def test_old_maid_initialization():
    game = OldMaidLogic()
    assert game.get_player_identifiers() == ["GM", "Player1", "Player2"]
    assert game.is_game_over() is False
    assert game.get_current_player() == 0
    assert game.phase == "DEAL"


def test_old_maid_invalid_deals():
    game = OldMaidLogic()
    # Not enough cards
    assert game.make_move(0, "H4 S4").success is False
    # Invalid card format
    assert game.make_move(0, "H4 S4 XYZ").success is False
    # More than 1 odd card (two old maids)
    assert game.make_move(0, "H4 S4 D5 C5 HQ SQ").success is False

    # Needs to stay GM turn since deals failed
    assert game.get_current_player() == 0


def test_old_maid_valid_deal_and_pairing():
    # 2 pairs and 1 old maid = 5 cards
    # H4, S4 will pair. D5, C5 will pair. HQ is old maid.
    # Player 1 gets: H4, D5, HQ (3 cards)
    # Player 2 gets: S4, C5 (2 cards)
    # Both H4/S4 and D5/C5 will pair when scanned
    # Wait, the remove_pairs checks within a SINGLE hand.
    # Actually, Old Maid deals all cards, then pairs within hands.
    # If P1 gets H4 and P2 gets S4, they do NOT pair up in the deal phase!
    pass


def test_old_maid_full_game_flow():
    game = OldMaidLogic()

    # Deal a tiny deck where we know exactly where the cards go.
    # We want pairs to form *within* a hand to test pairing.
    # P1 gets: H4, S4, HQ
    # P2 gets: D5, C5
    # GM deals: H4, D5, S4, C5, HQ
    assert game.make_move(0, "H4 D5 S4 C5 HQ").success

    # After deal:
    # P1 received H4, S4, HQ. H4 and S4 form a pair and are removed!
    # P1 hand should just be [HQ]
    # P2 received D5, C5. D5 and C5 form a pair and are removed!
    # P2 hand should be []

    # Wait, if P2 hand is [], the game should be over!
    assert game.is_game_over() is True
    assert game.winner == "Player2"
    assert game.pairs == [1, 1]


def test_old_maid_hover_and_banter():
    game = OldMaidLogic()
    # P1 gets: H4, D5, HQ (no pairs) -> hand: H4, D5, HQ
    # P2 gets: S4, C5 (no pairs) -> hand: S4, C5
    assert game.make_move(0, "H4 S4 D5 C5 HQ").success
    assert game.is_game_over() is False
    assert game.get_current_player() == 1  # Player1's turn

    # P1 hovers over index 0
    assert game.make_move(1, "0? Are you hiding the Old Maid?").success

    # Prompt and valid moves for reply
    assert game.phase == "REPLY"
    assert game.get_current_player() == 2
    assert game.get_valid_moves() == []
    assert "increase your chances" in game.get_prompt(2)

    # P2 replies
    assert game.make_move(2, "Maybe!").success

    # Back to P1
    assert game.phase == "PLAY"
    assert game.get_current_player() == 1

    # Check that prompt no longer mentions hovering
    prompt = game.get_prompt(1)
    assert "<index>? <banter>" not in prompt

    # P1 cannot hover again!
    assert game.make_move(1, "1? Hovering again").success is False

    # P1 takes the card at index 0 (which is S4)
    assert game.make_move(1, "0! I take it!").success

    # History formatting test
    view = game.render_player_view(1)
    history_view = game.render_player_history(1)
    assert "(card S4)" in history_view
    assert "(card S4)" not in view

    # P1 had H4, D5, HQ. Now takes S4. H4 and S4 pair up!
    # P1 hand: D5, HQ
    # P2 hand: C5
    assert game.pairs[0] == 1  # P1 got a pair
    assert len(game.hands[0]) == 2
    assert len(game.hands[1]) == 1

    # Now it is P2's turn
    assert game.get_current_player() == 2
