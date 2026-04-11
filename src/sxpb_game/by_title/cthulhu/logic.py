import os
import sys
import random
from typing import List, Optional, Tuple

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))
from game_eval.logic import GameLogic, MoveResult, read_rulebook


class CthulhuLogic(GameLogic):
    def __init__(self, num_players: int = 4):
        self.num_players = max(3, num_players - 1)
        self.phase = "DEAL_ROLES"  # DEAL_ROLES, DEAL_CARDS, PLAY, REPLY, GROUP_REPLY
        self.turn = 0  # Player index (0 to N-1) who has the flashlight
        self.target_player = None  # For REPLY phase
        self.reply_queue = []  # For GROUP_REPLY phase

        self.round_number = 1
        self.reveals_this_round = 0
        self.elder_signs_found = 0

        self.turn_group_questions = 0
        self.turn_direct_questions = 0
        self.round_group_question_asked = False

        self.game_over = False
        self.result = None

        self.roles = []
        self.hands = [[] for _ in range(self.num_players)]

        self.history = []

    def get_player_identifiers(self) -> List[str]:
        return ["GM"] + [f"p{i + 1}" for i in range(self.num_players)]

    def get_visible_players(self, player_idx: int) -> List[int]:
        return [i for i in range(1, self.num_players + 1)]

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
        if self.phase in ["DEAL_ROLES", "DEAL_CARDS"]:
            return 0
        if self.phase == "PLAY":
            return self.turn + 1
        if self.phase == "REPLY":
            return (self.target_player or 0) + 1
        if self.phase == "GROUP_REPLY":
            return self.reply_queue[0] + 1 if self.reply_queue else self.turn + 1
        return None

    def get_prompt(self, player_idx: int) -> str:
        if player_idx == 0:
            if self.phase == "DEAL_ROLES":
                return "Deal roles (Investigator/Cultist space-separated)."
            return f"Deal cards for Round {self.round_number} (ElderSign/Blank/Cthulhu space-separated)."

        if self.phase == "PLAY":
            prompt = (
                "You have the flashlight. Pick a player to reveal a card from.\n"
                "- To reveal a card, respond with `p<idx>! <optional banter>` "
                f"(idx 1 to {self.num_players}, exclude yourself)."
            )

            if self.turn_direct_questions < 3:
                prompt += (
                    "\n- To hover and banter first, respond with `p<idx>? <banter>`."
                )

            if self.turn_group_questions < 1:
                prompt += "\n- To ask the group a question and have everyone reply, respond with `??? <optional banter>`."

                if not self.round_group_question_asked:
                    prompt += "\n\nCards have been re-dealt for this round. It would be a good idea to ask everyone to share information about their new hands if they haven't already!"

            return prompt

        if self.phase == "REPLY":
            return "Someone hovered over you and asked a question or bantered. Reply to them."
        if self.phase == "GROUP_REPLY":
            return "The player with the flashlight asked the group a question. Reply to them."

        return "Wait."

    def make_move(self, player_idx: int, move: str) -> MoveResult:
        if self.is_game_over() or player_idx != self.get_current_player():
            return MoveResult(False, "")

        if player_idx == 0:
            parts = move.split()
            if self.phase == "DEAL_ROLES":
                if len(parts) != self.num_players:
                    return MoveResult(False, "")
                self.roles = parts
                self.phase = "DEAL_CARDS"
                return MoveResult(True, "")

            if self.phase == "DEAL_CARDS":
                expected_cards = self.num_players * (6 - self.round_number)
                if len(parts) != expected_cards:
                    return MoveResult(False, "")

                # Deal evenly
                self.hands = [[] for _ in range(self.num_players)]
                cards_per_player = 6 - self.round_number
                for i in range(self.num_players):
                    self.hands[i] = parts[
                        i * cards_per_player : (i + 1) * cards_per_player
                    ]

                self.phase = "PLAY"
                self.reveals_this_round = 0
                self.turn_group_questions = 0
                self.turn_direct_questions = 0
                self.round_group_question_asked = False
                self.history.append("((event deal_cards))")
                self.history.append(f"(round {self.round_number})")
                return MoveResult(True, "")

        if player_idx > 0:
            p_turn = player_idx - 1
            p_str = f"p{player_idx}"

            if self.phase == "REPLY":
                self.history.append(f'({p_str} "{move}")')
                self.phase = "PLAY"
                return MoveResult(True, "")

            if self.phase == "GROUP_REPLY":
                self.history.append(f'({p_str} "{move}")')
                if self.reply_queue:
                    self.reply_queue.pop(0)
                if not self.reply_queue:
                    self.phase = "PLAY"
                return MoveResult(True, "")

            if self.phase == "PLAY":
                if move.startswith("???"):
                    if self.turn_group_questions >= 1:
                        return MoveResult(False, "")

                    self.turn_group_questions += 1
                    self.round_group_question_asked = True
                    # Queue everyone else to reply, starting with the next player
                    self.reply_queue = [
                        (p_turn + i) % self.num_players
                        for i in range(1, self.num_players)
                    ]
                    self.phase = "GROUP_REPLY"
                    self.history.append(f'({p_str} "{move}")')
                    return MoveResult(True, "")

                parts = move.split(maxsplit=2)
                if not parts:
                    return MoveResult(False, "")

                action = parts[0]

                # Check for hover: `p2? banter`
                if action.endswith("?"):
                    target_str = action
                    is_hover = True
                else:
                    # Must be a reveal: `p2!`
                    is_hover = False

                if is_hover:
                    if self.turn_direct_questions >= 3:
                        return MoveResult(False, "")

                    if not target_str.lower().startswith("p"):
                        return MoveResult(False, "")
                    idx_str = target_str[1:-1]
                    try:
                        target_p_id = int(idx_str)
                        target_idx = target_p_id - 1
                    except ValueError:
                        return MoveResult(False, "")

                    if (
                        target_idx < 0
                        or target_idx >= self.num_players
                        or target_idx == p_turn
                    ):
                        return MoveResult(False, "")
                    if len(self.hands[target_idx]) == 0:
                        return MoveResult(False, "")

                    self.turn_direct_questions += 1
                    self.target_player = target_idx
                    self.phase = "REPLY"
                    self.history.append(f'({p_str} "{move}")')
                    return MoveResult(True, "")

                # Handling Reveal: `p2!`
                target_str = action

                if not target_str.lower().startswith("p"):
                    return MoveResult(False, "")

                if not target_str.endswith("!") and "!" not in target_str:
                    return MoveResult(False, "")

                target_str = target_str.split("!")[0]

                try:
                    target_p_id = int(target_str[1:])
                    target_idx = target_p_id - 1
                except ValueError:
                    return MoveResult(False, "")

                if (
                    target_idx < 0
                    or target_idx >= self.num_players
                    or target_idx == p_turn
                ):
                    return MoveResult(False, "")
                if len(self.hands[target_idx]) == 0:
                    return MoveResult(False, "")

                card_idx = 0  # Randomize by just taking the first one
                drawn = self.hands[target_idx].pop(card_idx)

                self.history.append(f'({p_str} "{move}")')
                self.history.append(f"(reveal p{target_p_id} {drawn})")

                self.turn = target_idx
                self.reveals_this_round += 1
                self.turn_group_questions = 0
                self.turn_direct_questions = 0

                if drawn == "Cthulhu":
                    self.game_over = True
                    self.result = "Cultists"
                elif drawn == "ElderSign":
                    self.elder_signs_found += 1
                    if self.elder_signs_found == self.num_players:
                        self.game_over = True
                        self.result = "Investigators"

                if not self.game_over and self.reveals_this_round == self.num_players:
                    self.round_number += 1
                    if self.round_number > 4:
                        self.game_over = True
                        self.result = "Cultists"
                    else:
                        self.phase = "DEAL_CARDS"

                return MoveResult(True, "")

        return MoveResult(False, "")

    def render_player_history(self, player_idx: int) -> str:
        board = ""
        if self.history:
            h_lines = []
            cur_line = []
            for h in self.history:
                if h.startswith("(round "):
                    if cur_line:
                        h_lines.append(" ".join(cur_line))
                        cur_line = []
                    h_lines.append(h)
                else:
                    cur_line.append(h)
                    if h.startswith("(reveal "):
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
        board = "(table\n"
        board += f" (flashlight p{self.turn + 1})\n"
        board += f" (turn_countdown {self.num_players - self.reveals_this_round})\n"
        board += f" (round_countdown {5 - self.round_number})\n"
        board += f" (elder_sign_reveal_count {self.elder_signs_found})\n"
        board += " (hand_by_player ()\n"

        for i in range(self.num_players):
            p_id = i + 1
            if player_idx == 0 or player_idx == p_id or self.is_game_over():
                board += f"  (p{p_id}\n"
                role = self.roles[i] if self.roles else "unknown"
                board += f"   (role {role})\n"

                blanks = self.hands[i].count("Blank")
                cthulhus = self.hands[i].count("Cthulhu")
                elders = self.hands[i].count("ElderSign")

                board += f"   (blank_count {blanks})\n"
                board += f"   (cthulhu_count {cthulhus})\n"
                board += f"   (elder_sign_count {elders})\n"
                board += "  )\n"
            else:
                board += f"  (p{p_id} (count {len(self.hands[i])}))\n"

        board += " )\n"
        board += ")\n\n"

        board += f"(elder_sign_total {self.num_players})\n"

        pools = {
            3: (2, 2),  # Good, Evil
            4: (3, 2),
            5: (4, 2),
            6: (4, 2),
            7: (5, 3),
            8: (6, 3),
        }
        good_pool, evil_pool = pools.get(
            self.num_players, (self.num_players, max(2, (self.num_players + 1) // 2))
        )
        pool_size = good_pool + evil_pool
        left_out = pool_size - self.num_players
        min_evil = max(0, evil_pool - left_out)
        max_evil = min(self.num_players, evil_pool)

        board += f"(cultist_count_range (min {min_evil}) (max {max_evil}))\n"

        return board

    def get_rules(self) -> str:
        return read_rulebook(__file__)

    def get_algorithm_move(
        self, player_idx: int, algorithm: str
    ) -> Tuple[Optional[str], Optional[str]]:
        if algorithm != "random":
            return super().get_algorithm_move(player_idx, algorithm)

        if player_idx == 0:
            if self.phase == "DEAL_ROLES":
                pools = {
                    3: (2, 2),
                    4: (3, 2),
                    5: (4, 2),
                    6: (4, 2),
                    7: (5, 3),
                    8: (6, 3),
                }
                good, evil = pools.get(
                    self.num_players,
                    (self.num_players, max(2, (self.num_players + 1) // 2)),
                )
                pool = ["Investigator"] * good + ["Cultist"] * evil
                roles = random.sample(pool, self.num_players)
                return " ".join(roles), None

            if self.phase == "DEAL_CARDS":
                if self.round_number == 1:
                    pool = (
                        ["ElderSign"] * self.num_players
                        + ["Cthulhu"]
                        + ["Blank"] * (self.num_players * 4 - 1)
                    )
                else:
                    pool = [c for hand in self.hands for c in hand]
                random.shuffle(pool)
                return " ".join(pool), None

        if player_idx > 0:
            p_turn = player_idx - 1
            if self.phase in ["REPLY", "GROUP_REPLY"]:
                return "I have no idea what you're talking about.", None

            if self.phase == "PLAY":
                # Find a valid target with cards
                valid_targets = [
                    i
                    for i in range(self.num_players)
                    if i != p_turn and len(self.hands[i]) > 0
                ]
                if not valid_targets:
                    return None, "No valid moves available."
                target = random.choice(valid_targets)

                # Bot has a small chance to ask the group a question
                if self.turn_group_questions < 1 and random.random() < 0.1:
                    return "??? Who has the elder signs?", None

                return f"p{target + 1}!", None

        return None, "Invalid state for algorithm."
