import os
import sys
import random
from typing import List, Optional, Tuple

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))
from sxpb_game.eval.logic import GameLogic, MoveResult

SUITS = ["S", "H", "D", "C"]
RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]


class OldMaidLogic(GameLogic):
    def __init__(self):
        self.hands = [[], []]  # Player 1 and Player 2
        self.pairs = [0, 0]
        self.game_over = False
        self.result = None
        self.phase = "DEAL"  # DEAL, PLAY, INSERT
        self.turn = 0  # 0 for P1, 1 for P2
        self.drawn_card = None
        self.old_maid = None

        self.hover_exchange_done = False
        self.history = []

    def get_player_identifiers(self) -> List[str]:
        return ["GM", "Player1", "Player2"]

    def get_visible_players(self, player_idx: int) -> List[int]:
        return [1, 2]

    @property
    def winner(self) -> Optional[str]:
        if not self.game_over:
            return None
        return self.result

    def is_game_over(self) -> bool:
        return self.game_over

    def get_current_player(self) -> Optional[int]:
        if self.is_game_over():
            return None
        if self.phase == "DEAL":
            return 0
        if self.phase in ["PLAY", "INSERT", "REPLY"]:
            return self.turn + 1  # 1 for P1, 2 for P2
        return None

    def get_prompt(self, player_idx: int) -> str:
        if player_idx == 0:
            return "Deal the cards."

        player_turn = player_idx - 1

        if self.phase == "PLAY":
            opp_idx = 1 - player_turn
            num_cards = len(self.hands[opp_idx])
            prompt = f"Pick a card from Player {opp_idx + 1}'s hand by choosing a valid index (0 to {num_cards - 1}).\n- To take a card, respond with `<index>! <optional banter>`"
            if not getattr(self, "hover_exchange_done", False):
                prompt += "\n- To hover over a card and say some banter in an attempt to sus out information, respond with `<index>? <banter>`"
            return prompt

        if self.phase == "REPLY":
            return "The other player hovered over a card and said something. Reply by saying something to increase your chances of victory."

        if self.phase == "INSERT":
            return f"You picked the old maid ({self.drawn_card}). Pick an index to insert it into your hand (0 to {len(self.hands[player_turn])})."

        return "Wait."

    def _remove_pairs(self, hand_idx: int):
        hand = self.hands[hand_idx]
        new_hand = []
        for card in hand:
            r = card[1:]
            paired = False
            for i, saved_card in enumerate(new_hand):
                if saved_card[1:] == r:
                    new_hand.pop(i)
                    self.pairs[hand_idx] += 1
                    paired = True
                    break
            if not paired:
                new_hand.append(card)
        self.hands[hand_idx] = new_hand

    def _check_game_over(self):
        if len(self.hands[0]) == 0:
            self.game_over = True
            self.result = "Player1"
        elif len(self.hands[1]) == 0:
            self.game_over = True
            self.result = "Player2"

    def get_valid_moves(self):
        if self.phase == "REPLY":
            return []
        if self.phase == "PLAY":
            opp_idx = 1 - self.turn
            return [str(i) for i in range(len(self.hands[opp_idx]))]
        if self.phase == "INSERT":
            return [str(i) for i in range(len(self.hands[self.turn]) + 1)]
        return []

    def make_move(self, player_idx: int, move: str) -> MoveResult:
        if self.is_game_over() or player_idx != self.get_current_player():
            return MoveResult(False, "")

        if player_idx == 0:
            # GM move
            cards = move.split()
            if len(cards) < 3:
                return MoveResult(False, "")

            # Count ranks to find old maid
            rank_counts = {}
            for card in cards:
                if len(card) < 2 or card[0] not in SUITS or card[1:] not in RANKS:
                    return MoveResult(False, "")
                r = card[1:]
                rank_counts[r] = rank_counts.get(r, 0) + 1

            # Ensure pairs + 1 old maid
            odds = 0
            for r, c in rank_counts.items():
                if c % 2 != 0:
                    odds += 1

            if odds != 1:
                return MoveResult(False, "")

            # Alternate dealing
            for i, card in enumerate(cards):
                self.hands[i % 2].append(card)

            # Identify old maid
            for card in cards:
                if rank_counts[card[1:]] % 2 != 0:
                    self.old_maid = card
                    break

            # Remove initial pairs
            self._remove_pairs(0)
            self._remove_pairs(1)

            self._check_game_over()
            if not self.game_over:
                self.phase = "PLAY"
                self.turn = 0
            return MoveResult(True, "")

        # Player move
        if player_idx in [1, 2]:
            p_turn = player_idx - 1
            p_str = f"p{player_idx}"

            if self.phase == "REPLY":
                self.history.append(f'({p_str} "{move}")')
                self.phase = "PLAY"
                self.turn = 1 - self.turn
                return MoveResult(True, "")

            if self.phase == "PLAY":
                parts = move.split(maxsplit=1)
                if not parts:
                    return MoveResult(False, "")
                action = parts[0]

                opp_idx = 1 - p_turn

                if action.endswith("?"):
                    if getattr(self, "hover_exchange_done", False):
                        return MoveResult(False, "")

                    idx_str = action[:-1]
                    if (
                        not idx_str.isdigit()
                        or int(idx_str) < 0
                        or int(idx_str) >= len(self.hands[opp_idx])
                    ):
                        return MoveResult(False, "")

                    self.hover_exchange_done = True
                    self.phase = "REPLY"
                    self.turn = 1 - self.turn
                    self.history.append(f'({p_str} "{move}")')
                    return MoveResult(True, "")

                elif action.endswith("!"):
                    idx_str = action[:-1]
                    if (
                        not idx_str.isdigit()
                        or int(idx_str) < 0
                        or int(idx_str) >= len(self.hands[opp_idx])
                    ):
                        return MoveResult(False, "")

                    idx = int(idx_str)
                    drawn = self.hands[opp_idx].pop(idx)

                    self.history.append(f'({p_str} "{move}")')
                    self.history.append(f"(card {drawn})")

                    self.hover_exchange_done = False

                    # Check if it's old maid
                    if self.old_maid and drawn[1:] == self.old_maid[1:]:
                        self.drawn_card = drawn
                        self.phase = "INSERT"
                    else:
                        self.hands[p_turn].append(drawn)
                        self._remove_pairs(p_turn)
                        self.turn = 1 - self.turn
                        self._check_game_over()
                    return MoveResult(True, "")
                else:
                    return MoveResult(False, "")

            if self.phase == "INSERT":
                valid_indices = [str(i) for i in range(len(self.hands[p_turn]) + 1)]
                if move in valid_indices:
                    idx = int(move)
                elif move.endswith("!") and move[:-1] in valid_indices:
                    idx = int(move[:-1])
                else:
                    return MoveResult(False, "")

                self.hands[p_turn].insert(idx, self.drawn_card)
                self.drawn_card = None
                self.phase = "PLAY"
                self.turn = 1 - self.turn
                self._check_game_over()
                return MoveResult(True, "")

        return MoveResult(False, "")

    def render_player_history(self, player_idx: int) -> str:
        board = ""
        if self.history:
            h_lines = []
            cur_line = []
            for h in self.history:
                cur_line.append(h)
                if h.startswith("(card "):
                    h_lines.append(" ".join(cur_line))
                    cur_line = []
            if cur_line:
                h_lines.append(" ".join(cur_line))
            history_str = "\n  ".join(h_lines)
            board += f"((history)\n  {history_str}\n)"
        else:
            board += "((history))"
        return board

    def render_player_view(self, player_idx: int) -> str:
        # GM sees everything
        if player_idx == 0:
            p1_disp = " ".join(self.hands[0])
            p2_disp = " ".join(self.hands[1])
        elif player_idx == 1:
            p1_disp = " ".join(self.hands[0])
            p2_disp = " ".join(["?" for _ in self.hands[1]])
        elif player_idx == 2:
            p1_disp = " ".join(["?" for _ in self.hands[0]])
            p2_disp = " ".join(self.hands[1])
        else:
            p1_disp = " ".join(["?" for _ in self.hands[0]])
            p2_disp = " ".join(["?" for _ in self.hands[1]])

        p1_pairs = self.pairs[0]
        p2_pairs = self.pairs[1]

        board = "; --- Old Maid ---\n"
        board += "(board\n"
        board += f" (p1_cards (()) {p1_disp})\n"
        board += f" (p2_cards (()) {p2_disp})\n"
        if self.phase == "INSERT":
            if self.turn == 0 and player_idx in [0, 1]:
                board += f" (drawn_card {self.drawn_card})\n"
            elif self.turn == 1 and player_idx in [0, 2]:
                board += f" (drawn_card {self.drawn_card})\n"
        board += ")\n"
        board += f"(pair_count_by_player () (p1 {p1_pairs}) (p2 {p2_pairs}))\n"
        return board

    def __str__(self):
        return self.render_player_view(0)

    def get_algorithm_move(
        self, player_idx: int, algorithm: str
    ) -> Tuple[Optional[str], Optional[str]]:
        if algorithm != "random":
            return super().get_algorithm_move(player_idx, algorithm)

        if player_idx == 0:
            deck = [s + r for s in SUITS for r in RANKS]
            # Remove one queen
            deck.remove("SQ")
            random.shuffle(deck)
            return " ".join(deck), None

        if player_idx in [1, 2]:
            moves = self.get_valid_moves()
            if not moves:
                return None, "No valid moves available."
            move = random.choice(moves)
            if self.phase == "PLAY":
                move += "!"
            return move, None

        return None, "Invalid player index."
