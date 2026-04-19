import os
import sys
import random
from typing import Any, Dict, List, Optional, Tuple

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from game_eval.logic import GameLogic, MoveResult, read_rulebook


class SkullLogic(GameLogic):
    def __init__(self, num_players: int = 4):
        self.num_players = max(3, num_players - 1)
        self.game_over = False
        self._winner = None
        self.players: List[Dict[str, Any]] = [
            {
                "status": "active",
                "score": 0,
                "hand": {"skull": 1, "rose": 3},
                "stack": [],
            }
            for _ in range(self.num_players)
        ]

        self.round_num: int = 1
        self.phase: str = "FIRST_DISC"

        self.first_player: int = 0
        self.current_player: int = 0
        self.highest_bid: int = 0
        self.highest_bidder: Optional[int] = None
        self.passed_players: set[int] = set()

        self.flipped_so_far: int = 0
        self.hover_exchange_done: bool = False
        self.skull_owner_idx: int = 0

        self.history: List[str] = []

    def _record_move(self, p_name: str, raw_move: str):
        escaped = raw_move.replace('"', '\\"')
        lower_move = escaped.lower()
        if lower_move.startswith("play rose"):
            escaped = "play [redacted]" + escaped[9:]
        elif lower_move.startswith("play skull"):
            escaped = "play [redacted]" + escaped[10:]
        self.history.append(f'({p_name} "{escaped}")')

    def get_player_identifiers(self) -> List[str]:
        return ["GM"] + [f"p{i + 1}" for i in range(self.num_players)]

    def get_visible_players(self, player_idx: int) -> List[int]:
        return [i for i in range(1, self.num_players + 1)]

    def get_rules(self) -> str:
        return read_rulebook(__file__)

    def is_game_over(self) -> bool:
        return self.game_over

    def get_current_player(self) -> Optional[int]:
        if self.is_game_over():
            return None
        if self.phase == "CHALLENGER_RANDOM_DISCARD":
            return 0
        return self.current_player + 1

    def _next_active_player(self, start_idx: int) -> int:
        idx = (start_idx + 1) % self.num_players
        while self.players[idx]["status"] != "active":
            idx = (idx + 1) % self.num_players
        return idx

    def _active_players_count(self) -> int:
        return sum(1 for p in self.players if p["status"] == "active")

    def _total_discs_on_table(self) -> int:
        return sum(len(p["stack"]) for p in self.players)

    def _return_discs_to_hands(self):
        for p in self.players:
            for d in p["stack"]:
                if isinstance(d, tuple):
                    d = d[1]
                p["hand"][d] += 1
            p["stack"] = []

    def _start_new_round(self, first_player: int):
        self.round_num += 1
        self.first_player = first_player
        self.current_player = first_player
        self.highest_bid = 0
        self.highest_bidder = None
        self.passed_players = set()
        self.flipped_so_far = 0
        self.hover_exchange_done = False

        self._return_discs_to_hands()

        self.phase = "FIRST_DISC"

    def get_prompt(self, player_idx: int) -> str:
        if player_idx == 0:
            if self.phase == "CHALLENGER_RANDOM_DISCARD":
                return (
                    "Provide random discard choice: 'discard rose' or 'discard skull'"
                )
            return "Wait"

        if self.phase == "FIRST_DISC":
            return "Everyone must play one disc to start the round. Reply with: `play rose <optional banter>` or `play skull <optional banter>`."
        elif self.phase == "PLAY_OR_BID":
            max_bid = self._total_discs_on_table()
            return f"You can play a disc (e.g., `play rose <banter>`) or start the bidding (e.g., `bid 1 <banter>`). Max bid is {max_bid}."
        elif self.phase == "BIDDING":
            max_bid = self._total_discs_on_table()
            return f"The highest bid is {self.highest_bid}. You can raise (e.g., `bid {self.highest_bid + 1} <banter>`) up to {max_bid} or `pass <banter>`."
        elif self.phase == "CHALLENGE_FLIP":
            prompt = "You are the Challenger. "
            my_stack = self.players[self.current_player]["stack"]
            if not all(isinstance(d, tuple) and d[0] == "flipped" for d in my_stack):
                prompt += "You must flip all of your own discs first. Reply: `flip my stack <optional banter>`."
            else:
                prompt += "Choose a player's stack to flip their top disc. Reply: `flip p<idx> <optional banter>`."
                if not self.hover_exchange_done:
                    prompt += "\nOptionally, you can hover and banter first: `p<idx>? <banter>`."
            return prompt
        elif self.phase == "CHALLENGE_HOVER_REPLY":
            return "The Challenger hovered over you. Reply to them to mindgame."
        elif self.phase == "DISCARD_DISC":
            return "You failed the challenge on your own skull. Choose a disc to discard permanently. Reply: `discard rose` or `discard skull`."
        return ""

    def make_move(self, player_idx: int, move: str) -> MoveResult:
        if self.is_game_over() or player_idx != self.get_current_player():
            return MoveResult(False, "Not your turn.")

        move_lower = move.lower().strip()

        if player_idx == 0:
            if self.phase == "CHALLENGER_RANDOM_DISCARD":
                assert self.highest_bidder is not None
                challenger_idx = self.highest_bidder
                challenger = self.players[challenger_idx]
                if move_lower == "discard rose" and challenger["hand"]["rose"] > 0:
                    discarded = "rose"
                elif move_lower == "discard skull" and challenger["hand"]["skull"] > 0:
                    discarded = "skull"
                else:
                    return MoveResult(False, "Invalid random discard choice.")

                challenger["hand"][discarded] -= 1
                if sum(challenger["hand"].values()) == 0:
                    challenger["status"] = "eliminated"
                    self.history.append(f"(p{challenger_idx + 1}_eliminated)")
                    if self._active_players_count() == 1:
                        self.game_over = True
                        self._winner = (
                            f"p{self._next_active_player(challenger_idx) + 1}"
                        )
                        return MoveResult(True, "")

                next_first = (
                    self.skull_owner_idx
                    if self.players[self.skull_owner_idx]["status"] == "active"
                    else self._next_active_player(self.skull_owner_idx)
                )
                self._start_new_round(next_first)
                return MoveResult(True, "")
            return MoveResult(False, "GM cannot move right now.")

        p_idx = player_idx - 1
        p_name = f"p{player_idx}"
        p = self.players[p_idx]

        if self.phase == "DISCARD_DISC":
            if move_lower.startswith("discard rose") and p["hand"]["rose"] > 0:
                p["hand"]["rose"] -= 1
            elif move_lower.startswith("discard skull") and p["hand"]["skull"] > 0:
                p["hand"]["skull"] -= 1
            else:
                return MoveResult(
                    False,
                    "Invalid discard. Must be 'discard rose' or 'discard skull' and you must have that disc.",
                )

            if sum(p["hand"].values()) == 0:
                p["status"] = "eliminated"
                self.history.append(f"({p_name}_eliminated)")
                if self._active_players_count() == 1:
                    self.game_over = True
                    self._winner = f"p{self._next_active_player(p_idx) + 1}"
                    return MoveResult(True, "")

            self._start_new_round(self._next_active_player(p_idx))
            return MoveResult(True, "")

        if self.phase == "CHALLENGE_HOVER_REPLY":
            self._record_move(p_name, move)
            self.phase = "CHALLENGE_FLIP"
            assert self.highest_bidder is not None
            self.current_player = self.highest_bidder
            return MoveResult(True, "")

        if self.phase in ["FIRST_DISC", "PLAY_OR_BID"]:
            if move_lower.startswith("play rose") or move_lower.startswith(
                "play skull"
            ):
                disc_type = "rose" if move_lower.startswith("play rose") else "skull"

                if p["hand"][disc_type] <= 0:
                    return MoveResult(False, f"You don't have a {disc_type} to play.")

                p["hand"][disc_type] -= 1
                p["stack"].append(disc_type)

                self._record_move(p_name, move)

                # Check next phase
                if self.phase == "FIRST_DISC":
                    next_p = self._next_active_player(self.current_player)
                    if next_p == self.first_player:
                        self.phase = "PLAY_OR_BID"
                    self.current_player = next_p
                else:  # PLAY_OR_BID
                    self.current_player = self._next_active_player(self.current_player)
                    # If all players have no cards, next must bid
                    if all(
                        sum(p2["hand"].values()) == 0
                        for p2 in self.players
                        if p2["status"] == "active"
                    ):
                        # Next player MUST bid, but we can just leave phase as PLAY_OR_BID and force bid in logic
                        pass
                return MoveResult(True, "")

            elif self.phase == "PLAY_OR_BID" and move_lower.startswith("bid "):
                parts = move[4:].strip().split(" ", 1)
                if not parts[0].isdigit():
                    return MoveResult(False, "Invalid bid number.")
                bid_amt = int(parts[0])

                max_bid = self._total_discs_on_table()
                if bid_amt <= 0 or bid_amt > max_bid:
                    return MoveResult(False, f"Bid must be between 1 and {max_bid}.")

                self.highest_bid = bid_amt
                self.highest_bidder = self.current_player
                self.phase = "BIDDING"

                self._record_move(p_name, move)

                if bid_amt == max_bid:
                    self._transition_to_challenge_flip()
                else:
                    self.current_player = self._next_active_player(self.current_player)
                return MoveResult(True, "")

            return MoveResult(False, "Invalid action for this phase.")

        if self.phase == "BIDDING":
            if move_lower.startswith("bid "):
                parts = move[4:].strip().split(" ", 1)
                if not parts[0].isdigit():
                    return MoveResult(False, "Invalid bid number.")
                bid_amt = int(parts[0])

                max_bid = self._total_discs_on_table()
                if bid_amt <= self.highest_bid or bid_amt > max_bid:
                    return MoveResult(
                        False,
                        f"Bid must be between {self.highest_bid + 1} and {max_bid}.",
                    )

                self.highest_bid = bid_amt
                self.highest_bidder = self.current_player

                self._record_move(p_name, move)

                if bid_amt == max_bid:
                    self._transition_to_challenge_flip()
                else:
                    self.current_player = self._next_active_player(self.current_player)
                return MoveResult(True, "")

            elif move_lower.startswith("pass"):
                self.passed_players.add(self.current_player)

                self._record_move(p_name, move)

                if len(self.passed_players) >= self._active_players_count() - 1:
                    assert self.highest_bidder is not None
                    self.current_player = self.highest_bidder
                    self._transition_to_challenge_flip()
                else:
                    self.current_player = self._next_active_player(self.current_player)
                    while self.current_player in self.passed_players:
                        self.current_player = self._next_active_player(
                            self.current_player
                        )
                return MoveResult(True, "")

            return MoveResult(False, "Must bid higher or pass.")

        if self.phase == "CHALLENGE_FLIP":
            if move_lower.startswith("p") and "?" in move:
                if self.hover_exchange_done:
                    return MoveResult(False, "You already hovered.")
                target_str = move[: move.find("?")].strip()
                if not target_str.startswith("p") or not target_str[1:].isdigit():
                    return MoveResult(False, "Invalid hover target.")
                target_idx = int(target_str[1:])
                t_idx = target_idx - 1
                if (
                    t_idx < 0
                    or t_idx >= self.num_players
                    or self.players[t_idx]["status"] != "active"
                ):
                    return MoveResult(False, "Invalid target player.")

                self.hover_exchange_done = True
                self.phase = "CHALLENGE_HOVER_REPLY"
                self.current_player = t_idx
                self._record_move(p_name, move)
                return MoveResult(True, "")

            elif move_lower.startswith("flip p"):
                parts = move[5:].strip().split(" ", 1)
                target_str = parts[0]

                if not target_str.startswith("p") or not target_str[1:].isdigit():
                    return MoveResult(False, "Invalid flip target.")
                target_idx = int(target_str[1:])
                t_idx = target_idx - 1
                if (
                    t_idx < 0
                    or t_idx >= self.num_players
                    or self.players[t_idx]["status"] != "active"
                ):
                    return MoveResult(False, "Invalid target player.")

                my_stack = p["stack"]
                if any(not isinstance(d, tuple) for d in my_stack):
                    return MoveResult(
                        False, "You must flip all of your own discs first."
                    )

                target_stack = self.players[t_idx]["stack"]
                unflipped = [
                    i for i, d in enumerate(target_stack) if not isinstance(d, tuple)
                ]
                if not unflipped:
                    return MoveResult(False, "That player has no unflipped discs.")

                self.hover_exchange_done = False
                idx = unflipped[-1]
                disc = target_stack[idx]
                target_stack[idx] = ("flipped", disc)

                self._record_move(p_name, move)
                self.history.append(f"(disc {disc.capitalize()})")

                return self._resolve_flip(p_idx, t_idx, disc)

            return MoveResult(False, "Invalid challenge move.")

        return MoveResult(False, "Unknown phase.")

    def _transition_to_challenge_flip(self):
        self.phase = "CHALLENGE_FLIP"
        self.flipped_so_far = 0
        p_idx = self.highest_bidder
        assert p_idx is not None
        self.current_player = p_idx
        p = self.players[p_idx]
        p_name = f"p{p_idx + 1}"

        # Automatically flip own stack (bottom to top in the logic, top to bottom in real life)
        # In our implementation, p["stack"] is bottom-to-top.
        # We should flip from top-to-bottom.
        stack = p["stack"]
        unflipped_indices = [i for i, d in enumerate(stack) if not isinstance(d, tuple)]
        for i in reversed(unflipped_indices):
            disc = stack[i]
            stack[i] = ("flipped", disc)
            self.history.append(f'({p_name} "flip my stack")')
            self.history.append(f"(disc {disc.capitalize()})")

            self._resolve_flip(p_idx, p_idx, disc)
            if self.phase != "CHALLENGE_FLIP" or self.game_over:
                return

        if self.highest_bid == self._total_discs_on_table():
            for target_idx, target_p in enumerate(self.players):
                if target_idx == p_idx or target_p["status"] != "active":
                    continue
                target_stack = target_p["stack"]
                unflipped = [
                    i for i, d in enumerate(target_stack) if not isinstance(d, tuple)
                ]
                for i in reversed(unflipped):
                    disc = target_stack[i]
                    target_stack[i] = ("flipped", disc)
                    self.history.append(f'({p_name} "flip p{target_idx + 1}")')
                    self.history.append(f"(disc {disc.capitalize()})")

                    self._resolve_flip(p_idx, target_idx, disc)
                    if self.phase != "CHALLENGE_FLIP" or self.game_over:
                        return

    def _resolve_flip(
        self, challenger_idx: int, owner_idx: int, disc: str
    ) -> MoveResult:
        if disc == "skull":
            self.history.append("(challenge_failed skull_flipped)")
            self._return_discs_to_hands()
            if challenger_idx == owner_idx:
                self.phase = "DISCARD_DISC"
                return MoveResult(True, "")
            else:
                # Target randomly discards one of the challenger's discs via GM (p0)
                self.skull_owner_idx = owner_idx
                self.phase = "CHALLENGER_RANDOM_DISCARD"
                return MoveResult(True, "")
        else:
            self.flipped_so_far += 1
            if self.flipped_so_far == self.highest_bid:
                self.history.append("(challenge_won)")
                self.players[challenger_idx]["score"] += 1
                if self.players[challenger_idx]["score"] == 2:
                    self.game_over = True
                    self._winner = f"p{challenger_idx + 1}"
                    return MoveResult(True, "")

                self._start_new_round(challenger_idx)
            return MoveResult(True, "")

    def render_player_history(self, player_idx: int) -> str:
        if not self.history:
            return "((history))"
        h_lines = "\n ".join(self.history[-20:])
        return f"((history)\n {h_lines}\n)"

    def render_player_view(self, player_idx: int) -> str:
        board = "; --- Skull ---\n\n(table\n"

        if not self.game_over:
            if self.phase in ["FIRST_DISC", "PLAY_OR_BID"]:
                board += (
                    f" ((phase_as stack)\n  (player p{self.current_player + 1})\n )\n"
                )
            elif self.phase == "BIDDING":
                assert self.highest_bidder is not None
                board += f" ((phase_as challenge)\n  (bid {self.highest_bid})\n  (player p{self.current_player + 1})\n  (challenger p{self.highest_bidder + 1})\n )\n"
            elif self.phase in ["CHALLENGE_FLIP", "CHALLENGE_HOVER_REPLY"]:
                board += f" ((phase_as flip)\n  (player p{self.current_player + 1})\n  (flip_countdown {self.highest_bid - self.flipped_so_far})\n )\n"
            elif self.phase in ["DISCARD_DISC", "CHALLENGER_RANDOM_DISCARD"]:
                board += (
                    f" ((phase_as discard)\n  (player p{self.current_player + 1})\n )\n"
                )

        board += " (stack_by_player ()\n"
        for i, p in enumerate(self.players):
            if p["status"] != "active":
                continue
            stack_disp = []
            for d in p["stack"]:
                if isinstance(d, tuple):
                    stack_disp.append(d[1].capitalize())
                elif i == player_idx - 1:
                    stack_disp.append(d.capitalize())
                else:
                    stack_disp.append("?")
            if not stack_disp:
                board += f"  (p{i + 1} (()))\n"
            else:
                board += f"  (p{i + 1} (()) {' '.join(stack_disp)})\n"
        board += " )\n"

        board += " (hand_by_player ()\n"
        for i, p in enumerate(self.players):
            if p["status"] != "active":
                continue
            if i == player_idx - 1:
                board += f"  (p{i + 1} (skull_count {p['hand']['skull']}) (rose_count {p['hand']['rose']}))\n"
            else:
                board += f"  (p{i + 1} (count {sum(p['hand'].values())}))\n"
        board += " )\n"

        board += " (score_by_player ()\n"
        for i, p in enumerate(self.players):
            if p["status"] != "active":
                continue
            board += f"  (p{i + 1} {p['score']})\n"
        board += " )\n)\n"

        if self.game_over:
            board += f"\n(status GAME_OVER)\n(winner {self._winner})\n"
        else:
            board += "\n(status PLAYING)\n"

        return board

    def get_valid_moves(self) -> List[str]:
        if self.is_game_over():
            return []
        if self.phase == "CHALLENGER_RANDOM_DISCARD":
            return ["discard rose", "discard skull"]
        p = self.players[self.current_player]
        moves = []
        if self.phase == "DISCARD_DISC":
            if p["hand"]["rose"] > 0:
                moves.append("discard rose")
            if p["hand"]["skull"] > 0:
                moves.append("discard skull")
            return moves

        if self.phase == "CHALLENGE_HOVER_REPLY":
            return ["<any text>"]

        if self.phase in ["FIRST_DISC", "PLAY_OR_BID"]:
            if p["hand"]["rose"] > 0:
                moves.append("play rose")
            if p["hand"]["skull"] > 0:
                moves.append("play skull")
            if self.phase == "PLAY_OR_BID":
                max_bid = self._total_discs_on_table()
                for b in range(1, max_bid + 1):
                    moves.append(f"bid {b}")
            if not moves:
                if self.phase == "FIRST_DISC":
                    moves.append("play rose")
                else:
                    moves.append("bid 1")
            return moves

        if self.phase == "BIDDING":
            max_bid = self._total_discs_on_table()
            moves.append("pass")
            for b in range(self.highest_bid + 1, max_bid + 1):
                moves.append(f"bid {b}")
            return moves

        if self.phase == "CHALLENGE_FLIP":
            targets = [
                i
                for i, p2 in enumerate(self.players)
                if p2["status"] == "active"
                and any(not isinstance(d, tuple) for d in p2["stack"])
            ]
            for t in targets:
                moves.append(f"flip p{t + 1}")
                if not self.hover_exchange_done:
                    moves.append(f"p{t + 1}?")
            return moves

        return []

    def get_algorithm_move(
        self, player_idx: int, algorithm: str
    ) -> Tuple[Optional[str], Optional[str]]:
        if algorithm != "random":
            return super().get_algorithm_move(player_idx, algorithm)

        if player_idx == 0:
            if self.phase == "CHALLENGER_RANDOM_DISCARD":
                assert self.highest_bidder is not None
                challenger = self.players[self.highest_bidder]
                choices = []
                if challenger["hand"]["rose"] > 0:
                    choices.append("discard rose")
                if challenger["hand"]["skull"] > 0:
                    choices.append("discard skull")
                if choices:
                    return random.choice(choices), None
            return None, "GM cannot move right now."

        p_idx = player_idx - 1
        p = self.players[p_idx]
        if self.phase == "DISCARD_DISC":
            if p["hand"]["rose"] > 0:
                return "discard rose", None
            return "discard skull", None

        if self.phase == "CHALLENGE_HOVER_REPLY":
            return "I have nothing to say.", None

        if self.phase in ["FIRST_DISC", "PLAY_OR_BID"]:
            choices = []
            if p["hand"]["rose"] > 0:
                choices.append("play rose")
            if p["hand"]["skull"] > 0:
                choices.append("play skull")

            if self.phase == "PLAY_OR_BID":
                max_bid = self._total_discs_on_table()
                if max_bid > 0:
                    choices.append("bid 1")

            if not choices:
                # Must bid
                if self.phase == "FIRST_DISC":
                    return "play rose", None  # This shouldn't happen, but just in case
                return "bid 1", None
            return random.choice(choices), None

        if self.phase == "BIDDING":
            max_bid = self._total_discs_on_table()
            choices = ["pass"]
            if self.highest_bid < max_bid:
                choices.append(f"bid {self.highest_bid + 1}")
            return random.choice(choices), None

        if self.phase == "CHALLENGE_FLIP":
            targets = [
                i
                for i, p2 in enumerate(self.players)
                if p2["status"] == "active"
                and any(not isinstance(d, tuple) for d in p2["stack"])
            ]
            if not targets:
                return None, "No valid targets."
            return f"flip p{random.choice(targets) + 1}", None

        return None, "Random algorithm could not determine move."
