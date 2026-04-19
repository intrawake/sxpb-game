import os
import sys
import random
from typing import List, Optional, Tuple

# Ensure we can import from src
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))
from game_eval.logic import GameLogic, MoveResult

SUITS = ["S", "H", "D", "C"]
RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
VALUES = {
    "2": 2,
    "3": 3,
    "4": 4,
    "5": 5,
    "6": 6,
    "7": 7,
    "8": 8,
    "9": 9,
    "10": 10,
    "J": 10,
    "Q": 10,
    "K": 10,
    "A": 11,
}


def get_deck(num_decks=6):
    return [s + r for s in SUITS for r in RANKS for _ in range(num_decks)]


def hand_value(hand):
    val, aces = 0, 0
    for card in hand:
        rank = card[1:]
        val += VALUES[rank]
        if rank == "A":
            aces += 1
    while val > 21 and aces > 0:
        val -= 10
        aces -= 1
    return val


def is_soft(hand):
    v, a_count = 0, 0
    for card in hand:
        r = card[1:]
        if r == "A":
            a_count += 1
        else:
            v += VALUES[r]
    v += a_count * 11
    effective_aces = a_count
    while v > 21 and effective_aces > 0:
        v -= 10
        effective_aces -= 1
    return effective_aces > 0


class BlackjackLogic(GameLogic):
    def __init__(self, num_decks=6):
        self.num_decks = num_decks
        self.dealer_hand = []
        self.player_hand = []
        self.game_over = False
        self.result = None
        self.history = []

        self.used_cards = []
        self.phase = "INITIAL_DEAL"  # INITIAL_DEAL, PLAYER_ACTION, DEAL_TO_PLAYER, DEALER_PLAY, GAME_OVER
        self.doubled = False

    def get_player_identifiers(self) -> List[str]:
        return ["GM", "Player"]

    @property
    def winner(self) -> Optional[str]:
        if not self.game_over:
            return None
        if self.result in ["WIN", "BLACKJACK"]:
            return "Player"
        elif self.result == "LOSS":
            return "GM"
        elif self.result == "PUSH":
            return "Draw"
        return None

    def is_game_over(self) -> bool:
        return self.phase == "GAME_OVER"

    def get_current_player(self) -> Optional[int]:
        if self.is_game_over():
            return None
        if self.phase in ["INITIAL_DEAL", "DEAL_TO_PLAYER", "DEALER_PLAY"]:
            return 0
        elif self.phase == "PLAYER_ACTION":
            return 1
        return None

    def get_prompt(self, player_idx: int) -> str:
        if player_idx == 0:
            if self.phase == "INITIAL_DEAL":
                target = (
                    "Player"
                    if len(self.player_hand) == len(self.dealer_hand)
                    else "Dealer"
                )
                return f"Deal a card to {target}."
            elif self.phase == "DEAL_TO_PLAYER":
                return "Deal a card to Player."
            elif self.phase == "DEALER_PLAY":
                return "Deal a card to Dealer."
        return "What is your move?"

    def _check_blackjack(self):
        p_val, d_val = hand_value(self.player_hand), hand_value(self.dealer_hand)
        if p_val == 21 or d_val == 21:
            if p_val == 21 and d_val == 21:
                self.result = "PUSH"
            elif p_val == 21:
                self.result = "BLACKJACK"
            else:
                self.result = "LOSS"
            self.phase = "GAME_OVER"
            self.game_over = True
            return True
        return False

    def _evaluate_winner(self):
        d_val, p_val = hand_value(self.dealer_hand), hand_value(self.player_hand)
        self.phase = "GAME_OVER"
        self.game_over = True
        if d_val > 21:
            self.result = "WIN"
        elif d_val > p_val:
            self.result = "LOSS"
        elif d_val < p_val:
            self.result = "WIN"
        else:
            self.result = "PUSH"

    def get_valid_moves(self):
        if self.phase == "PLAYER_ACTION":
            moves = ["hit", "stand"]
            if len(self.player_hand) == 2:
                moves.append("double")
            return moves
        elif self.phase in ["INITIAL_DEAL", "DEAL_TO_PLAYER", "DEALER_PLAY"]:
            # GM valid moves: any card not yet dealt (simplified: any card format)
            # Actually we can just return any valid card format
            pass
        return []

    def make_move(self, player_idx: int, move: str) -> MoveResult:
        action = move
        if self.is_game_over() or player_idx != self.get_current_player():
            return MoveResult(False, "")

        if player_idx == 0:
            # GM deals a card
            card = action.strip().upper()
            if len(card) < 2 or card[0] not in SUITS or card[1:] not in RANKS:
                return MoveResult(False, "")

            # Allow multiple decks, so we don't strictly enforce used_cards unless we want to simulate num_decks
            # For simplicity, we just accept the valid card.
            self.used_cards.append(card)

            if self.phase == "INITIAL_DEAL":
                if len(self.player_hand) == len(self.dealer_hand):
                    self.player_hand.append(card)
                else:
                    self.dealer_hand.append(card)

                if len(self.dealer_hand) == 2:
                    if not self._check_blackjack():
                        self.phase = "PLAYER_ACTION"
            elif self.phase == "DEAL_TO_PLAYER":
                self.player_hand.append(card)
                if hand_value(self.player_hand) > 21:
                    self.result, self.phase, self.game_over = "LOSS", "GAME_OVER", True
                elif self.doubled:
                    if hand_value(self.dealer_hand) >= 17:
                        self._evaluate_winner()
                    else:
                        self.phase = "DEALER_PLAY"
                else:
                    self.phase = "PLAYER_ACTION"
            elif self.phase == "DEALER_PLAY":
                self.dealer_hand.append(card)
                if hand_value(self.dealer_hand) >= 17:
                    self._evaluate_winner()
            return MoveResult(True, "")

        if player_idx == 1:
            action = action.lower().strip()
            # Map single letters for convenience
            if action == "h":
                action = "hit"
            elif action == "s":
                action = "stand"
            elif action == "d":
                action = "double"

            if action not in self.get_valid_moves():
                return MoveResult(False, "")

            self.history.append(action)
            if action == "hit":
                self.phase = "DEAL_TO_PLAYER"
            elif action == "stand":
                if hand_value(self.dealer_hand) >= 17:
                    self._evaluate_winner()
                else:
                    self.phase = "DEALER_PLAY"
            elif action == "double":
                self.doubled = True
                self.phase = "DEAL_TO_PLAYER"
            return MoveResult(True, "")

        return MoveResult(False, "")

    def render_player_view(self, player_idx: int) -> str:
        if player_idx == 0:
            # GM sees everything
            dealer_display = " ".join(self.dealer_hand) if self.dealer_hand else ""
            player_display = " ".join(self.player_hand) if self.player_hand else ""
        else:
            dealer_display = (
                f"{self.dealer_hand[0]} ?"
                if not self.game_over and len(self.dealer_hand) >= 2
                else " ".join(self.dealer_hand)
            )
            if not self.dealer_hand:
                dealer_display = ""
            elif len(self.dealer_hand) == 1:
                dealer_display = f"{self.dealer_hand[0]}"

            player_display = " ".join(self.player_hand) if self.player_hand else ""

        player_val = hand_value(self.player_hand)
        soft_str = " (Soft)" if is_soft(self.player_hand) else ""
        return f"""; --- Blackjack (6 Decks) ---
(board
 (dealer (()) {dealer_display})
 (player (()) {player_display}) ; Total: {player_val}{soft_str}
)"""

    def __str__(self):
        return self.render_player_view(1)

    def get_algorithm_move(
        self, player_idx: int, algorithm: str
    ) -> Tuple[Optional[str], Optional[str]]:
        if algorithm != "random":
            return super().get_algorithm_move(player_idx, algorithm)

        if player_idx == 0:
            # GM random deal
            available_cards = get_deck(self.num_decks)
            for uc in self.used_cards:
                if uc in available_cards:
                    available_cards.remove(uc)
            if not available_cards:
                # Reshuffle? Just give a random valid card to prevent crash
                available_cards = get_deck(1)
            return random.choice(available_cards), None

        if player_idx == 1:
            moves = self.get_valid_moves()
            if not moves:
                return None, "No valid moves available."
            return random.choice(moves), None

        return None, "Invalid player index."
