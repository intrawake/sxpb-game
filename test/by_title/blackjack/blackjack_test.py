import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from sxpb_game.by_title.blackjack.logic import BlackjackLogic


def test_blackjack_winner():
    game = BlackjackLogic()

    # Test Player Win
    game.dealer_hand, game.player_hand = ["S10", "D9"], ["H10", "CJ"]
    game._evaluate_winner()
    assert game.winner == "Player", f"Expected Player, got {game.winner}"

    # Test Dealer Win (Player Bust)
    game = BlackjackLogic()
    game.dealer_hand, game.player_hand = ["S10", "D9"], ["H10", "C5", "S8"]
    game.result = "LOSS"
    game.phase = "GAME_OVER"
    game.game_over = True
    assert game.winner == "GM", f"Expected GM, got {game.winner}"

    # Test Push
    game = BlackjackLogic()
    game.dealer_hand, game.player_hand = ["S10", "D9"], ["H10", "C9"]
    game._evaluate_winner()
    assert game.winner == "Draw", f"Expected Draw, got {game.winner}"

    # Test Blackjack
    game = BlackjackLogic()
    game.dealer_hand, game.player_hand = ["S10", "D9"], ["HA", "CK"]
    game._check_blackjack()
    assert game.winner == "Player", f"Expected Player, got {game.winner}"
    print("PASS: Blackjack winner properties match expected.")


if __name__ == "__main__":
    test_blackjack_winner()
