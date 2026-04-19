import os
import sys
import random
from typing import List, Optional, Tuple

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from game_eval.logic import GameLogic, MoveResult, read_rulebook


class ResistanceLogic(GameLogic):
    def __init__(self, num_players: int = 5):
        self.num_players = max(5, min(10, num_players - 1))

        self.spy_counts = {5: 2, 6: 2, 7: 3, 8: 3, 9: 3, 10: 4}
        self.squad_sizes = {
            5: [2, 3, 2, 3, 3],
            6: [2, 3, 4, 3, 4],
            7: [2, 3, 3, 4, 4],
            8: [3, 4, 4, 5, 5],
            9: [3, 4, 4, 5, 5],
            10: [3, 4, 4, 5, 5],
        }

        self.phase = "DEAL_ROLES"  # DEAL_ROLES, PROPOSE_SQUAD, VOTE_ON_SQUAD, MISSION_VOTE, DISCUSSION_ORDER, DISCUSSION, DISCUSSION_REPLY
        self.round = 1
        self.leader_idx = 0
        self.vote_track = 0

        self.teams = []
        self.proposed_squad = []
        self.completed_missions = []

        self.squad_votes = {}
        self.mission_votes = {}

        self.discussion_order = []
        self.discussion_idx = 0
        self.discussion_target = None
        self.turn_question_asked = False

        self.score_resistance = 0
        self.score_spies = 0
        self.game_over = False
        self.result = None
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
        if self.phase == "DEAL_ROLES":
            return 0
        if self.phase == "DISCUSSION_ORDER":
            return 0
        if self.phase == "DISCUSSION":
            return self.discussion_order[self.discussion_idx] + 1
        if self.phase == "DISCUSSION_REPLY":
            return (
                (self.discussion_target + 1)
                if self.discussion_target is not None
                else None
            )
        if self.phase == "PROPOSE_SQUAD":
            return self.leader_idx + 1
        if self.phase == "VOTE_ON_SQUAD":
            for i in range(self.num_players):
                if i not in self.squad_votes:
                    return i + 1
            return 0
        if self.phase == "MISSION_VOTE":
            for i in self.proposed_squad:
                if i not in self.mission_votes:
                    return i + 1
            return 0
        return None

    def get_prompt(self, player_idx: int) -> str:
        if player_idx == 0:
            if self.phase == "DEAL_ROLES":
                spy_count = self.spy_counts[self.num_players]
                return f"Deal roles. You need exactly {spy_count} Spy and {self.num_players - spy_count} Resistance. Format: 'Spy Resistance...'"
            if self.phase == "DISCUSSION_ORDER":
                return "Generate random order for the players (e.g. 'p3 p1 p4')."
            return "Wait."

        if self.phase == "DISCUSSION":
            prompt = "Discussion phase. "
            if not self.turn_question_asked:
                prompt += "You can ask one person a question by responding with `p<idx>? <question>`, OR "
            prompt += "Say something to the group, accuse someone, or defend yourself (this will end your turn)."
            return prompt

        if self.phase == "DISCUSSION_REPLY":
            return "Someone asked you a direct question. Reply to them."

        if self.phase == "PROPOSE_SQUAD":
            team_size = self.squad_sizes[self.num_players][self.round - 1]
            return f"You are the leader. Propose a squad of {team_size} players. Format: 'propose p1 p2...'"

        if self.phase == "VOTE_ON_SQUAD":
            squad_str = ", ".join([f"p{i + 1}" for i in self.proposed_squad])
            return f"Vote on the proposed squad: {squad_str}. Reply with 'vote approve' or 'vote reject'."

        if self.phase == "MISSION_VOTE":
            return (
                "You are on the mission! Reply with 'play success' or 'play sabotage'."
            )

        return "Wait."

    def make_move(self, player_idx: int, move: str) -> MoveResult:
        if self.is_game_over() or player_idx != self.get_current_player():
            return MoveResult(False, "Not your turn.")

        parts = move.split()
        if not parts:
            return MoveResult(False, "Empty move.")

        if player_idx == 0:
            if self.phase == "DEAL_ROLES":
                if len(parts) != self.num_players:
                    return MoveResult(False, f"Need {self.num_players} roles.")
                spy_count = self.spy_counts[self.num_players]
                if parts.count("Spy") != spy_count:
                    return MoveResult(False, f"Must have exactly {spy_count} Spies.")
                for r in parts:
                    if r not in ["Spy", "Resistance"]:
                        return MoveResult(False, "Roles must be Spy or Resistance.")
                self.teams = parts
                self.phase = "PROPOSE_SQUAD"
                return MoveResult(True, "")

            if self.phase == "DISCUSSION_ORDER":
                order = []
                for p in parts:
                    if p.startswith("p"):
                        try:
                            idx = int(p[1:]) - 1
                            if 0 <= idx < self.num_players and idx not in order:
                                order.append(idx)
                        except ValueError:
                            pass
                for i in range(self.num_players):
                    if i not in order:
                        order.append(i)
                order_str = " ".join([f"p{i + 1}" for i in order])
                self.history.append(f"((event order_players) (()) {order_str})")
                self.discussion_order = order
                self.discussion_idx = 0
                self.turn_question_asked = False
                self.phase = "DISCUSSION"
                return MoveResult(True, "")

            return MoveResult(False, "")

        p_idx = player_idx - 1
        move_lower = move.lower()

        if self.phase == "DISCUSSION_REPLY":
            self.history.append(f'(p{player_idx} "{move}")')
            self.phase = "DISCUSSION"
            return MoveResult(True, "")

        if self.phase == "DISCUSSION":
            parts_move = move.split(maxsplit=2)
            is_hover = False
            target_idx = -1
            if parts_move and parts_move[0].endswith("?"):
                target_str = parts_move[0]
                if target_str.lower().startswith("p"):
                    idx_str = target_str[1:-1]
                    try:
                        t_p_id = int(idx_str)
                        target_idx = t_p_id - 1
                        if 0 <= target_idx < self.num_players and target_idx != p_idx:
                            is_hover = True
                    except ValueError:
                        pass

            if is_hover:
                if self.turn_question_asked:
                    return MoveResult(False, "You already asked a question.")
                self.turn_question_asked = True
                self.discussion_target = target_idx
                self.phase = "DISCUSSION_REPLY"
                self.history.append(f'(p{player_idx} "{move}")')
                return MoveResult(True, "")

            # Normal discussion move
            self.history.append(f'(p{player_idx} "{move}")')
            self.discussion_idx += 1
            self.turn_question_asked = False

            if self.discussion_idx >= len(self.discussion_order):
                self.phase = "PROPOSE_SQUAD"
            return MoveResult(True, "")

        if self.phase == "PROPOSE_SQUAD":
            if parts[0].lower() != "propose":
                return MoveResult(False, "Must start with 'propose'.")
            team_size = self.squad_sizes[self.num_players][self.round - 1]
            squad = []
            for p in parts[1:]:
                if p.startswith("p"):
                    try:
                        idx = int(p[1:]) - 1
                        if 0 <= idx < self.num_players and idx not in squad:
                            squad.append(idx)
                    except ValueError:
                        pass
            if len(squad) != team_size:
                return MoveResult(
                    False, f"Must propose exactly {team_size} distinct players."
                )
            self.proposed_squad = squad
            squad_str = " ".join([f"p{i + 1}" for i in squad])
            self.history.append(f'(p{player_idx} "propose {squad_str}")')
            self.phase = "VOTE_ON_SQUAD"
            self.squad_votes = {p_idx: "approve"}
            self.history.append(f'(p{player_idx} "vote approve") ; private')
            return MoveResult(True, "")

        if self.phase == "VOTE_ON_SQUAD":
            if "approve" in move_lower:
                vote_val = "approve"
            elif "reject" in move_lower:
                vote_val = "reject"
            else:
                return MoveResult(False, "Must 'vote approve' or 'vote reject'.")

            self.squad_votes[p_idx] = vote_val
            self.history.append(f'(p{player_idx} "vote {vote_val}") ; private')

            if len(self.squad_votes) == self.num_players:
                votes_str = " ".join(
                    [
                        f"(p{i + 1} {self.squad_votes[i]})"
                        for i in range(self.num_players)
                    ]
                )
                self.history.append(f"((event squad_votes_revealed) (()) {votes_str})")

                approves = list(self.squad_votes.values()).count("approve")
                if approves > self.num_players / 2:
                    self.history.append("((event squad_approved))")
                    self.vote_track = 0
                    self.phase = "MISSION_VOTE"
                    self.mission_votes = {}
                    for p in self.proposed_squad:
                        if self.teams[p] == "Resistance":
                            self.mission_votes[p] = "success"
                            self.history.append(f'(p{p + 1} "play success") ; private')

                    if len(self.mission_votes) == len(self.proposed_squad):
                        self._resolve_mission()
                else:
                    self.history.append("((event squad_rejected))")
                    self.vote_track += 1
                    self.leader_idx = (self.leader_idx + 1) % self.num_players
                    self.proposed_squad = []
                    if self.vote_track >= 5:
                        self.game_over = True
                        self.result = "Spy"
                        self.history.append(
                            "((event game_over) (winning_team Spy) (reason vote_track_maxed))"
                        )
                    else:
                        self.phase = "DISCUSSION_ORDER"
            return MoveResult(True, "")

        if self.phase == "MISSION_VOTE":
            if p_idx not in self.proposed_squad:
                return MoveResult(False, "You are not on the squad.")

            if "success" in move_lower:
                play_val = "success"
            elif "sabotage" in move_lower:
                play_val = "sabotage"
            else:
                return MoveResult(False, "Must 'play success' or 'play sabotage'.")

            if self.teams[p_idx] == "Resistance" and play_val == "sabotage":
                return MoveResult(False, "Resistance players must play success.")

            self.mission_votes[p_idx] = play_val
            self.history.append(f'(p{player_idx} "play {play_val}") ; private')

            if len(self.mission_votes) == len(self.proposed_squad):
                self._resolve_mission()

            return MoveResult(True, "")

        return MoveResult(False, "Invalid move.")

    def _resolve_mission(self):
        sabotages = list(self.mission_votes.values()).count("sabotage")
        self.completed_missions.append(
            {"squad": self.proposed_squad.copy(), "sabotage_count": sabotages}
        )

        required_fails = 1
        if self.num_players >= 7 and self.round == 4:
            required_fails = 2

        self.history.append(f"((event mission_resolved) (sabotages {sabotages}))")

        if sabotages >= required_fails:
            self.score_spies += 1
            self.history.append("((event mission_failed))")
        else:
            self.score_resistance += 1
            self.history.append("((event mission_succeeded))")

        if self.score_resistance >= 3:
            self.game_over = True
            self.result = "Resistance"
            self.history.append("((event game_over) (winning_team Resistance))")
        elif self.score_spies >= 3:
            self.game_over = True
            self.result = "Spy"
            self.history.append("((event game_over) (winning_team Spy))")
        else:
            self.round += 1
            self.leader_idx = (self.leader_idx + 1) % self.num_players
            self.proposed_squad = []
            self.phase = "DISCUSSION_ORDER"

    def render_player_history(self, player_idx: int) -> str:
        if not self.history:
            return "((history))"

        h_lines = []
        is_gm = player_idx == 0
        is_over = self.is_game_over()

        for h in self.history:
            visible = False
            rendered = h

            if " ; private" in h:
                parts = h.split(" ; ", 1)
                base = parts[0].strip()
                actor_str = base.split(maxsplit=1)[0].strip("(")
                try:
                    a_idx = int(actor_str[1:]) - 1
                    is_self = player_idx == a_idx + 1
                    if is_gm or is_over or is_self:
                        visible = True
                        rendered = base
                except (ValueError, IndexError):
                    pass
            else:
                visible = True

            if visible:
                if not rendered.startswith("(") and not rendered.startswith(";"):
                    rendered = f"({rendered})"
                h_lines.append(rendered)

        history_str = "\n ".join(h_lines)
        return f"((history)\n {history_str}\n)"

    def render_player_view(self, player_idx: int) -> str:
        board = "(table\n"

        phase_name = self.phase
        if self.game_over:
            phase_name = "GAME_OVER"

        board += f" ((phase_as {phase_name})\n"
        if self.phase != "DEAL_ROLES" and not self.game_over:
            board += f"  (round {self.round})\n"
            team_size = self.squad_sizes[self.num_players][self.round - 1]
            board += f"  (team_size {team_size})\n"
            board += f"  (vote_track {self.vote_track})\n"
            if self.num_players >= 7 and self.round == 4:
                board += "  (requires_two_fails +true)\n"
        board += " )\n"

        if self.phase != "DEAL_ROLES":
            board += f" (leader p{self.leader_idx + 1})\n"

        if self.phase in ["DISCUSSION", "DISCUSSION_REPLY"]:
            if hasattr(self, "discussion_order") and self.discussion_order:
                rem = self.discussion_order[self.discussion_idx :]
                if rem:
                    order_str = " ".join([f"p{i + 1}" for i in rem])
                    board += f" (discussion_queue (()) {order_str})\n"

        if self.proposed_squad:
            squad_str = " ".join([f"p{i + 1}" for i in self.proposed_squad])
            board += f" (proposed_squad (()) {squad_str})\n"

        if self.completed_missions:
            board += " (completed_missions (())\n"
            for m in self.completed_missions:
                squad_str = " ".join([f"p{i + 1}" for i in m["squad"]])
                board += f"  (() (squad (()) {squad_str}) (sabotage_count {m['sabotage_count']}))\n"
            board += " )\n"

        board += " (score\n"
        board += f"  (resistance {self.score_resistance})\n"
        board += f"  (spies {self.score_spies})\n"
        board += " )\n"

        board += " (player_by_identifier ()\n"
        for i in range(self.num_players):
            p_id = i + 1
            show_team = False

            if self.is_game_over() or player_idx == 0 or player_idx == p_id:
                show_team = True
            elif player_idx > 0 and self.teams and self.teams[player_idx - 1] == "Spy":
                if self.teams[i] == "Spy":
                    show_team = True

            if show_team and self.teams:
                board += f"  (p{p_id} (team {self.teams[i]}))\n"
            else:
                board += f"  (p{p_id})\n"

        board += " )\n"
        board += ")\n"
        return board

    def get_rules(self) -> str:
        return read_rulebook(__file__)

    def get_valid_moves(self) -> List[str]:
        if self.is_game_over():
            return []

        if self.phase == "DEAL_ROLES":
            return ["Spy Resistance..."]

        p_idx = self.get_current_player()
        if p_idx == 0 or p_idx is None:
            return []

        p_idx -= 1

        if self.phase == "DISCUSSION":
            return ["<any text>", "pX? <any text>"]
        if self.phase == "DISCUSSION_REPLY":
            return ["<any text>"]

        if self.phase == "PROPOSE_SQUAD":
            return ["propose pX pY..."]

        if self.phase == "VOTE_ON_SQUAD":
            return ["vote approve", "vote reject"]

        if self.phase == "MISSION_VOTE":
            if self.teams and self.teams[p_idx] == "Resistance":
                return ["play success"]
            return ["play success", "play sabotage"]

        return []

    def get_algorithm_move(
        self, player_idx: int, algorithm: str
    ) -> Tuple[Optional[str], Optional[str]]:
        if algorithm != "random":
            return super().get_algorithm_move(player_idx, algorithm)

        if player_idx == 0:
            if self.phase == "DEAL_ROLES":
                spy_count = self.spy_counts[self.num_players]
                res_count = self.num_players - spy_count
                pool = ["Spy"] * spy_count + ["Resistance"] * res_count
                random.shuffle(pool)
                return " ".join(pool), None
            if self.phase == "DISCUSSION_ORDER":
                alive_p = [f"p{i + 1}" for i in range(self.num_players)]
                random.shuffle(alive_p)
                return " ".join(alive_p), None
            return None, "GM cannot move."

        p_idx = player_idx - 1

        if self.phase == "DISCUSSION":
            if not self.turn_question_asked and random.random() < 0.3:
                others = [i for i in range(self.num_players) if i != p_idx]
                target = random.choice(others)
                return f"p{target + 1}? Are you a spy?", None
            return "I am definitely Resistance.", None

        if self.phase == "DISCUSSION_REPLY":
            return "I don't know what you're talking about.", None

        if self.phase == "PROPOSE_SQUAD":
            team_size = self.squad_sizes[self.num_players][self.round - 1]
            pool = list(range(self.num_players))
            squad = random.sample(pool, team_size)
            squad_str = " ".join([f"p{i + 1}" for i in squad])
            return f"propose {squad_str}", None

        if self.phase == "VOTE_ON_SQUAD":
            return random.choice(["vote approve", "vote reject"]), None

        if self.phase == "MISSION_VOTE":
            if self.teams[p_idx] == "Resistance":
                return "play success", None
            else:
                return random.choice(["play success", "play sabotage"]), None

        return None, "Random algorithm failed."
