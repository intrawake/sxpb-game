import os
import sys
import random
from typing import List, Optional, Tuple

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from game_eval.logic import GameLogic, MoveResult, read_rulebook


class MafiaLogic(GameLogic):
    def __init__(self, num_players: int = 5):
        self.num_players = max(4, num_players - 1)
        # Phases: DEAL_ROLES, NIGHT_MAFIA_DISCUSSION, NIGHT_MAFIA_VOTE, NIGHT_DOCTOR, NIGHT_DETECTIVE, DAY_DISCUSSION, DAY_VOTE
        self.phase = "DEAL_ROLES"
        self.turn = 0  # Player index (0 to N-1) for sequential actions

        self.roles = []
        self.teams = []
        self.alive = [True] * self.num_players

        self.night_kill_target = None
        self.doctor_save_target = None
        self.detective_investigate_target = None
        self.detective_result = None
        self.vigilante_has_shot = False
        self.vigilante_target = None
        self.last_saved_player = None

        self.day_votes = {}
        self.night_votes = {}
        self.mafia_discussion_turns = 0

        self.discussion_order = []
        self.discussion_idx = 0
        self.discussion_target = None
        self.turn_question_asked = False
        self.day_discussion_round = 0
        self.vote_order = []
        self.vote_idx = 0

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

        if self.phase in ["NIGHT_MAFIA_DISCUSSION", "NIGHT_MAFIA_VOTE"]:
            return self.turn + 1

        if self.phase == "NIGHT_DOCTOR":
            for i, (role, is_alive) in enumerate(zip(self.roles, self.alive)):
                if role == "Doctor" and is_alive:
                    return i + 1
            return 0

        if self.phase == "NIGHT_DETECTIVE":
            for i, (role, is_alive) in enumerate(zip(self.roles, self.alive)):
                if role == "Detective" and is_alive:
                    return i + 1
            return 0

        if self.phase == "NIGHT_VIGILANTE":
            for i, (role, is_alive) in enumerate(zip(self.roles, self.alive)):
                if role == "Vigilante" and is_alive and not self.vigilante_has_shot:
                    return i + 1
            return 0

        if self.phase in ["DAY_ORDER", "DAY_VOTE_ORDER"]:
            return 0

        if self.phase == "DAY_DISCUSSION":
            return self.discussion_order[self.discussion_idx] + 1

        if self.phase == "DAY_DISCUSSION_REPLY":
            return (
                self.discussion_target + 1
                if self.discussion_target is not None
                else None
            )

        if self.phase == "DAY_VOTE":
            return (
                self.vote_order[self.vote_idx] + 1
                if self.vote_idx < len(self.vote_order)
                else None
            )

        return None

    def get_prompt(self, player_idx: int) -> str:
        if player_idx == 0:
            if self.phase in ["DAY_ORDER", "DAY_VOTE_ORDER"]:
                alive_p = [f"p{i + 1}" for i, a in enumerate(self.alive) if a]
                random.shuffle(alive_p)
                return " ".join(alive_p)

            if self.phase == "DEAL_ROLES":
                mafia_count = max(1, self.num_players // 3)
                return f"Deal roles (e.g. 'Mafia Villager Doctor Detective Villager'). You need {mafia_count} Mafia. Roles must match player count."
            if self.phase in ["NIGHT_DOCTOR", "NIGHT_DETECTIVE", "NIGHT_VIGILANTE"]:
                return "Role is dead or missing. Reply 'skip' to advance phase."
            if self.phase in ["DAY_ORDER", "DAY_VOTE_ORDER"]:
                return "Generate random order for the living players (e.g. 'p3 p1 p4')."

        if self.phase == "NIGHT_MAFIA_DISCUSSION":
            return "Night falls. You are the Mafia. Discuss with your fellow Mafia who to target. Do NOT cast a vote yet, just talk."

        if self.phase == "NIGHT_MAFIA_VOTE":
            return "You are the Mafia. Choose a player to kill (e.g. 'kill p2')."

        if self.phase == "NIGHT_DOCTOR":
            return "You are the Doctor. Choose a player to save tonight (e.g. 'save p2'). You can optionally add private banter."

        if self.phase == "NIGHT_DETECTIVE":
            return "You are the Detective. Choose a player to investigate (e.g. 'investigate p2'). You can optionally add private banter."

        if self.phase == "NIGHT_VIGILANTE":
            return "You are the Vigilante. Choose a player to shoot (e.g. 'shoot p2'), or 'skip' to save your bullet. You have 1 shot per game."

        if self.phase == "DAY_DISCUSSION":
            prompt = "Day discussion phase. "
            if not self.turn_question_asked:
                prompt += "You can ask one person a question by responding with `p<idx>? <question>`, OR "
            prompt += "Say something to the group, accuse someone, or defend yourself (this will end your turn)."
            return prompt

        if self.phase == "DAY_DISCUSSION_REPLY":
            return "Someone asked you a direct question. Reply to them."

        if self.phase == "DAY_VOTE":
            return (
                "Voting phase. Cast your vote to lynch (e.g. 'vote p2') or 'vote none'."
            )

        return "Wait."

    def check_win_condition(self):
        mafia_count = sum(
            1 for i, role in enumerate(self.roles) if role == "Mafia" and self.alive[i]
        )
        villager_count = sum(
            1 for i, role in enumerate(self.roles) if role != "Mafia" and self.alive[i]
        )

        if mafia_count == 0:
            self.game_over = True
            self.result = "Villagers"
            self.history.append("((event game_over) (winning_team Villagers))")
        elif mafia_count >= villager_count:
            self.game_over = True
            self.result = "Mafia"
            self.history.append("((event game_over) (winning_team Mafia))")

    def _next_alive_player(self, current: int) -> int:
        nxt = (current + 1) % self.num_players
        while not self.alive[nxt] and sum(self.alive) > 0:
            nxt = (nxt + 1) % self.num_players
        return nxt

    def _next_alive_mafia(self, current: int) -> int:
        nxt = (current + 1) % self.num_players
        while not (self.alive[nxt] and self.roles[nxt] == "Mafia") and any(
            a and r == "Mafia" for a, r in zip(self.alive, self.roles)
        ):
            nxt = (nxt + 1) % self.num_players
        return nxt

    def make_move(self, player_idx: int, move: str) -> MoveResult:
        if self.is_game_over() or player_idx != self.get_current_player():
            return MoveResult(False, "")

        parts = move.split()
        if not parts:
            return MoveResult(False, "")

        if player_idx == 0:
            if self.phase == "DEAL_ROLES":
                if len(parts) != self.num_players:
                    return MoveResult(False, "")
                self.roles = parts
                self.teams = ["Mafia" if r == "Mafia" else "Villager" for r in parts]
                self.phase = "NIGHT_MAFIA_DISCUSSION"
                self.history.append("((event night_falls))")

                # Start discussion with first alive Mafia
                self.turn = 0
                while not (self.alive[self.turn] and self.roles[self.turn] == "Mafia"):
                    self.turn += 1
                self.mafia_discussion_turns = 0
                self.night_votes = {}
                return MoveResult(True, "")

            if self.phase in ["NIGHT_DOCTOR", "NIGHT_DETECTIVE", "NIGHT_VIGILANTE"]:
                if parts[0].lower() == "skip":
                    if self.phase == "NIGHT_DOCTOR":
                        self.last_saved_player = None
                        det_exists = any(
                            r == "Detective" and a
                            for r, a in zip(self.roles, self.alive)
                        )
                        vig_exists = any(
                            r == "Vigilante" and a
                            for r, a in zip(self.roles, self.alive)
                        )
                        if det_exists:
                            self.phase = "NIGHT_DETECTIVE"
                        elif vig_exists:
                            self.phase = "NIGHT_VIGILANTE"
                        else:
                            self._resolve_night()
                    elif self.phase == "NIGHT_DETECTIVE":
                        vig_exists = any(
                            r == "Vigilante" and a
                            for r, a in zip(self.roles, self.alive)
                        )
                        if vig_exists:
                            self.phase = "NIGHT_VIGILANTE"
                        else:
                            self._resolve_night()
                    else:
                        self._resolve_night()
                    return MoveResult(True, "")
                return MoveResult(False, "")

            if self.phase in ["DAY_ORDER", "DAY_VOTE_ORDER"]:
                order = []
                for p in parts:
                    if p.startswith("p"):
                        try:
                            idx = int(p[1:]) - 1
                            if (
                                0 <= idx < self.num_players
                                and self.alive[idx]
                                and idx not in order
                            ):
                                order.append(idx)
                        except ValueError:
                            pass

                for i in range(self.num_players):
                    if self.alive[i] and i not in order:
                        order.append(i)

                order_str = " ".join([f"p{i + 1}" for i in order])
                self.history.append(f"((event order_players) (()) {order_str})")

                if self.phase == "DAY_ORDER":
                    self.discussion_order = order
                    self.discussion_idx = 0
                    self.turn_question_asked = False
                    self.phase = "DAY_DISCUSSION"
                else:
                    self.vote_order = order
                    self.vote_idx = 0
                    self.day_votes = {}
                    self.phase = "DAY_VOTE"

                return MoveResult(True, "")

        p_idx = player_idx - 1
        p_str = f"p{player_idx}"

        if self.phase == "NIGHT_MAFIA_DISCUSSION":
            self.history.append(f'({p_str} "{move}") ; private')
            self.mafia_discussion_turns += 1

            mafia_count = sum(
                1 for a, r in zip(self.alive, self.roles) if a and r == "Mafia"
            )

            if self.mafia_discussion_turns >= mafia_count:
                self.phase = "NIGHT_MAFIA_VOTE"
                # Reset turn back to first alive Mafia for voting
                self.turn = 0
                while not (self.alive[self.turn] and self.roles[self.turn] == "Mafia"):
                    self.turn += 1
            else:
                self.turn = self._next_alive_mafia(self.turn)
            return MoveResult(True, "")

        if self.phase == "NIGHT_MAFIA_VOTE":
            target_str = parts[0]
            if target_str.lower() == "kill" and len(parts) >= 2:
                target_str = parts[1]

            if not target_str.startswith("p"):
                return MoveResult(False, "")
            try:
                t_idx = int(target_str[1:].rstrip("!")) - 1
                if t_idx < 0 or t_idx >= self.num_players or not self.alive[t_idx]:
                    return MoveResult(False, "")
            except ValueError:
                return MoveResult(False, "")

            self.night_votes[p_idx] = t_idx
            self.history.append(f'(p{player_idx} "kill p{t_idx + 1}") ; Mafia')

            mafia_count = sum(
                1 for a, r in zip(self.alive, self.roles) if a and r == "Mafia"
            )
            if len(self.night_votes) >= mafia_count:
                # Tally votes and resolve
                vote_counts = {}
                for v in self.night_votes.values():
                    vote_counts[v] = vote_counts.get(v, 0) + 1

                max_votes = max(vote_counts.values())

                # Tie breaker: least-recently voted victim dies first
                candidates = [k for k, v in vote_counts.items() if v == max_votes]
                first_vote_index = {}
                for idx, (voter, vote) in enumerate(self.night_votes.items()):
                    if vote in candidates and vote not in first_vote_index:
                        first_vote_index[vote] = idx

                winner = sorted(candidates, key=lambda c: first_vote_index[c])[0]

                self.night_kill_target = winner
                self.history.append(
                    f"(Mafia_kill_decision p{self.night_kill_target + 1}) ; Mafia"
                )

                # Check if doctor exists and is alive
                doc_exists = any(
                    r == "Doctor" and a for r, a in zip(self.roles, self.alive)
                )
                det_exists = any(
                    r == "Detective" and a for r, a in zip(self.roles, self.alive)
                )
                vig_exists = any(
                    r == "Vigilante" and a for r, a in zip(self.roles, self.alive)
                )
                if doc_exists:
                    self.phase = "NIGHT_DOCTOR"
                elif det_exists:
                    self.phase = "NIGHT_DETECTIVE"
                elif vig_exists:
                    self.phase = "NIGHT_VIGILANTE"
                else:
                    self._resolve_night()
            else:
                self.turn = self._next_alive_mafia(self.turn)
            return MoveResult(True, "")

        if self.phase == "NIGHT_DOCTOR":
            if parts[0].lower() == "save" and len(parts) >= 2:
                target_str = parts[1]
                if not target_str.startswith("p"):
                    return MoveResult(False, "")
                try:
                    t_idx = int(target_str[1:]) - 1
                except ValueError:
                    return MoveResult(False, "")
                if t_idx < 0 or t_idx >= self.num_players or not self.alive[t_idx]:
                    return MoveResult(False, "")

                if getattr(self, "last_saved_player", None) == t_idx:
                    return MoveResult(
                        False, "Cannot save the same player on consecutive nights."
                    )

                self.doctor_save_target = t_idx
                self.last_saved_player = t_idx
                self.history.append(f'({p_str} "save p{t_idx + 1}") ; private')

                det_exists = any(
                    r == "Detective" and a for r, a in zip(self.roles, self.alive)
                )
                vig_exists = any(
                    r == "Vigilante" and a for r, a in zip(self.roles, self.alive)
                )
                if det_exists:
                    self.phase = "NIGHT_DETECTIVE"
                elif vig_exists:
                    self.phase = "NIGHT_VIGILANTE"
                else:
                    self._resolve_night()
                return MoveResult(True, "")

            # Fallback for LLMs that just send "p2" or "p2!"
            target_str = parts[0]
            if target_str.startswith("p"):
                try:
                    t_idx = int(target_str[1:].rstrip("!")) - 1
                    if 0 <= t_idx < self.num_players and self.alive[t_idx]:
                        if getattr(self, "last_saved_player", None) == t_idx:
                            return MoveResult(
                                False,
                                "Cannot save the same player on consecutive nights.",
                            )

                        self.doctor_save_target = t_idx
                        self.last_saved_player = t_idx
                        self.history.append(f'({p_str} "save p{t_idx + 1}") ; private')
                        det_exists = any(
                            r == "Detective" and a
                            for r, a in zip(self.roles, self.alive)
                        )
                        vig_exists = any(
                            r == "Vigilante" and a
                            for r, a in zip(self.roles, self.alive)
                        )
                        if det_exists:
                            self.phase = "NIGHT_DETECTIVE"
                        elif vig_exists:
                            self.phase = "NIGHT_VIGILANTE"
                        else:
                            self._resolve_night()
                        return MoveResult(True, "")
                except ValueError:
                    pass

        if self.phase == "NIGHT_DETECTIVE":
            if parts[0].lower() == "investigate" and len(parts) >= 2:
                target_str = parts[1]
                if not target_str.startswith("p"):
                    return MoveResult(False, "")
                try:
                    t_idx = int(target_str[1:]) - 1
                except ValueError:
                    return MoveResult(False, "")
                if t_idx < 0 or t_idx >= self.num_players or not self.alive[t_idx]:
                    return MoveResult(False, "")

                is_mafia = self.roles[t_idx] == "Mafia"
                result = "Mafia" if is_mafia else "Not_Mafia"
                self.history.append(
                    f'(p{player_idx} "investigate p{t_idx + 1}") ; Detective result {result}'
                )

                vig_exists = any(
                    r == "Vigilante" and a for r, a in zip(self.roles, self.alive)
                )
                if vig_exists:
                    self.phase = "NIGHT_VIGILANTE"
                else:
                    self._resolve_night()
                return MoveResult(True, "")

            # Fallback for LLMs that just send "p2" or "p2!"
            target_str = parts[0]
            if target_str.startswith("p"):
                try:
                    t_idx = int(target_str[1:].rstrip("!")) - 1
                    if 0 <= t_idx < self.num_players and self.alive[t_idx]:
                        is_mafia = self.roles[t_idx] == "Mafia"
                        result = "Mafia" if is_mafia else "Not_Mafia"
                        self.history.append(
                            f'({p_str} "investigate p{t_idx + 1}") ; Detective result {result}'
                        )
                        vig_exists = any(
                            r == "Vigilante" and a
                            for r, a in zip(self.roles, self.alive)
                        )
                        if vig_exists:
                            self.phase = "NIGHT_VIGILANTE"
                        else:
                            self._resolve_night()
                        return MoveResult(True, "")
                except ValueError:
                    pass

        if self.phase == "NIGHT_VIGILANTE":
            if parts[0].lower() == "skip":
                self.history.append(f'({p_str} "skip") ; private')
                self._resolve_night()
                return MoveResult(True, "")
            if parts[0].lower() == "shoot" and len(parts) >= 2:
                target_str = parts[1]
                if not target_str.startswith("p"):
                    return MoveResult(False, "")
                try:
                    t_idx = int(target_str[1:]) - 1
                except ValueError:
                    return MoveResult(False, "")
                if t_idx < 0 or t_idx >= self.num_players or not self.alive[t_idx]:
                    return MoveResult(False, "")

                self.vigilante_target = t_idx
                self.vigilante_has_shot = True
                self.history.append(f'({p_str} "shoot p{t_idx + 1}") ; private')
                self._resolve_night()
                return MoveResult(True, "")

            # Fallback
            target_str = parts[0]
            if target_str.startswith("p"):
                try:
                    t_idx = int(target_str[1:].rstrip("!")) - 1
                    if 0 <= t_idx < self.num_players and self.alive[t_idx]:
                        self.vigilante_target = t_idx
                        self.vigilante_has_shot = True
                        self.history.append(f'({p_str} "shoot p{t_idx + 1}") ; private')
                        self._resolve_night()
                        return MoveResult(True, "")
                except ValueError:
                    pass

        if self.phase == "DAY_DISCUSSION_REPLY":
            self.history.append(f'({p_str} "{move}")')
            self.phase = "DAY_DISCUSSION"
            return MoveResult(True, "")

        if self.phase == "DAY_DISCUSSION":
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
                        if (
                            0 <= target_idx < self.num_players
                            and self.alive[target_idx]
                            and target_idx != p_idx
                        ):
                            is_hover = True
                    except ValueError:
                        pass

            if is_hover:
                if self.turn_question_asked:
                    return MoveResult(False, "")
                self.turn_question_asked = True
                self.discussion_target = target_idx
                self.phase = "DAY_DISCUSSION_REPLY"
                self.history.append(f'({p_str} "{move}")')
                return MoveResult(True, "")

            # Normal discussion move
            self.history.append(f'({p_str} "{move}")')
            self.discussion_idx += 1
            self.turn_question_asked = False

            if self.discussion_idx >= len(self.discussion_order):
                self.day_discussion_round += 1
                if self.day_discussion_round < 2:
                    self.phase = "DAY_ORDER"
                else:
                    self.phase = "DAY_VOTE_ORDER"
                    self.day_discussion_round = 0
            return MoveResult(True, "")

        if self.phase == "DAY_VOTE":
            if parts[0].lower() == "vote":
                if len(parts) < 2:
                    return MoveResult(False, "")
                target_str = parts[1]
                if target_str.lower() == "none":
                    self.day_votes[p_idx] = None
                    self.history.append(f'({p_str} "vote none")')
                else:
                    if not target_str.startswith("p"):
                        return MoveResult(False, "")
                    try:
                        t_idx = int(target_str[1:]) - 1
                    except ValueError:
                        return MoveResult(False, "")
                    if t_idx < 0 or t_idx >= self.num_players or not self.alive[t_idx]:
                        return MoveResult(False, "")

                    self.day_votes[p_idx] = t_idx
                    self.history.append(f'({p_str} "vote p{t_idx + 1}")')

                self.vote_idx += 1

                # Check if everyone alive has voted
                alive_count = sum(self.alive)
                if len(self.day_votes) == alive_count or self.vote_idx >= len(
                    self.vote_order
                ):
                    self._resolve_vote()

                return MoveResult(True, "")

        return MoveResult(False, "")

    def _resolve_night(self):
        self.history.append("((event day_breaks))")
        deaths = []
        if (
            self.night_kill_target is not None
            and self.night_kill_target != self.doctor_save_target
        ):
            if self.night_kill_target not in deaths:
                deaths.append(self.night_kill_target)
        if (
            getattr(self, "vigilante_target", None) is not None
            and self.vigilante_target != self.doctor_save_target
        ):
            if self.vigilante_target not in deaths:
                deaths.append(self.vigilante_target)

        if deaths:
            for d in deaths:
                self.alive[d] = False
                self.history.append(f"((event death) (player p{d + 1}))")
        else:
            self.history.append("((event no_deaths))")

        self.night_kill_target = None
        self.doctor_save_target = None
        self.detective_result = None
        self.vigilante_target = None

        self.night_votes = {}

        self.check_win_condition()
        if not self.game_over:
            self.phase = "DAY_ORDER"
            self.day_discussion_round = 0

    def _resolve_vote(self):
        vote_counts = {}
        for v in self.day_votes.values():
            vote_counts[v] = vote_counts.get(v, 0) + 1

        if not vote_counts:
            self.history.append("((event no_lynch))")
        else:
            max_votes = max(vote_counts.values())

            if max_votes > 0:
                # Find the least recently voted-for candidate among those tied for max votes
                # To do this, we need to look at the order votes were cast.
                # Dicts in python 3.7+ preserve insertion order, so we can just iterate backwards.
                winner = None

                if None in vote_counts and vote_counts[None] == max_votes:
                    # Abstain wins ties
                    winner = None
                else:
                    # Find candidate who reached max_votes FIRST (least recently voted)
                    # Actually, the requirement says "tied victim who got voted least-recently will die"
                    # This means the person who received their *first* vote earlier among the tied candidates.
                    # Let's iterate through the vote history to find the first vote for each tied candidate.
                    candidates = [k for k, v in vote_counts.items() if v == max_votes]

                    first_vote_index = {}
                    for idx, (voter, vote) in enumerate(self.day_votes.items()):
                        if vote in candidates and vote not in first_vote_index:
                            first_vote_index[vote] = idx

                    # Sort candidates by their first vote index (ascending = least recently voted)
                    winner = sorted(candidates, key=lambda c: first_vote_index[c])[0]

                if winner is None:
                    self.history.append("((event no_lynch))")
                else:
                    lynched = winner
                    self.alive[lynched] = False
                    team = (
                        self.teams[lynched]
                        if hasattr(self, "teams")
                        else self.roles[lynched]
                    )
                    self.history.append(
                        f"((event lynch) (player p{lynched + 1}) (team {team}))"
                    )
            else:
                self.history.append("((event no_lynch))")

        self.check_win_condition()
        if not self.game_over:
            self.phase = "NIGHT_MAFIA_DISCUSSION"
            self.history.append("((event night_falls))")
            self.mafia_discussion_turns = 0
            self.night_votes = {}
            self.turn = 0
            while not (self.alive[self.turn] and self.roles[self.turn] == "Mafia"):
                self.turn += 1

    def render_player_history(self, player_idx: int) -> str:
        # History filtering and reformatting based on role
        if not self.history:
            return "((history))"

        h_lines = []
        my_role = self.roles[player_idx - 1] if player_idx > 0 and self.roles else None
        is_gm = player_idx == 0
        is_over = self.is_game_over()

        for h in self.history:
            visible = False
            rendered = h

            if " ; " in h:
                parts = h.split(" ; ", 1)
                base = parts[0].strip()
                comment = parts[1].strip()

                # Extract actor
                actor = base.split(maxsplit=1)[0].strip("(")
                a_idx = -1
                if actor.startswith("p"):
                    try:
                        a_idx = int(actor[1:]) - 1
                    except ValueError:
                        pass
                is_self = player_idx == a_idx + 1

                if comment.lower() == "private":
                    if is_gm or is_over or is_self:
                        visible = True
                        rendered = base
                elif comment.lower().startswith("mafia"):
                    if is_gm or is_over or my_role == "Mafia" or is_self:
                        visible = True
                        rendered = base
                        if actor == "Mafia_kill_decision":
                            rendered = f"((event mafia_kill_decision) {base.split(maxsplit=1)[1].strip(')')})"
                elif "detective result" in comment.lower():
                    if is_gm or is_over or is_self:
                        visible = True
                        rendered = h.strip()
                else:
                    # Fallback for other comments
                    visible = True
                    rendered = base
            else:
                # Events or other non-commented entries
                visible = True
                rendered = h

            if visible:
                # Final cleanup: ensure single ( ) wrapping if not an event
                if not rendered.startswith("(") and not rendered.startswith(";"):
                    rendered = f"({rendered})"
                h_lines.append(rendered)

        history_str = "\n ".join(h_lines)
        return f"((history)\n {history_str}\n)"

    def render_player_view(self, player_idx: int) -> str:
        board = "(table\n"
        board += f" (phase {self.phase})\n"

        investigated_p_ids = set()
        if player_idx > 0 and self.roles and self.roles[player_idx - 1] == "Detective":
            for h in self.history:
                if h.startswith(f"(p{player_idx} ") and "investigate p" in h:
                    for p_id in range(1, self.num_players + 1):
                        if f"investigate p{p_id}" in h:
                            investigated_p_ids.add(p_id)
        if self.phase in ["DAY_DISCUSSION", "DAY_DISCUSSION_REPLY"]:
            if hasattr(self, "discussion_order") and self.discussion_order:
                rem = self.discussion_order[self.discussion_idx :]
                if rem:
                    order_str = " ".join([f"p{i + 1}" for i in rem])
                    board += f" (discussion_queue (()) {order_str})\n"
        board += " (players ()\n"

        for i in range(self.num_players):
            p_id = i + 1
            status = "alive" if self.alive[i] else "dead"

            board += f"  (p{p_id} (status {status})"

            if hasattr(self, "teams") and self.teams and self.roles:
                my_team = self.teams[player_idx - 1] if player_idx > 0 else None
                is_gm = player_idx == 0
                is_self = player_idx == p_id
                is_game_over = self.is_game_over()
                is_same_mafia = my_team == "Mafia" and self.teams[i] == "Mafia"
                is_dead = not self.alive[i]

                show_team = False
                show_role = False

                if is_game_over or is_gm or is_self or is_same_mafia:
                    show_team = True
                    show_role = True
                elif p_id in investigated_p_ids:
                    show_team = True
                elif is_dead:
                    show_team = True

                if show_team:
                    board += f" (team {self.teams[i]})"
                if show_role:
                    board += f" (role {self.roles[i]})"
            elif self.roles:
                # Fallback if teams aren't initialized
                if (
                    player_idx == 0
                    or self.is_game_over()
                    or player_idx == p_id
                    or (
                        player_idx > 0
                        and self.roles[player_idx - 1] == "Mafia"
                        and self.roles[i] == "Mafia"
                    )
                ):
                    board += f" (role {self.roles[i]})"

            board += ")\n"

        board += " )\n)\n"
        return board

    def get_rules(self) -> str:
        mafia_count = max(1, self.num_players // 3)
        return read_rulebook(__file__).format(mafia_count=mafia_count)

    def get_algorithm_move(
        self, player_idx: int, algorithm: str
    ) -> Tuple[Optional[str], Optional[str]]:
        if algorithm != "random":
            return super().get_algorithm_move(player_idx, algorithm)

        if player_idx == 0:
            if self.phase in ["DAY_ORDER", "DAY_VOTE_ORDER"]:
                alive_p = [f"p{i + 1}" for i, a in enumerate(self.alive) if a]
                random.shuffle(alive_p)
                return " ".join(alive_p), None

            if self.phase == "DEAL_ROLES":
                mafia_count = max(1, self.num_players // 3)
                specials = []
                if self.num_players >= 4:
                    specials.append("Doctor")
                if self.num_players >= 5:
                    specials.append("Detective")
                if self.num_players >= 6:
                    specials.append("Vigilante")
                villager_count = max(0, self.num_players - mafia_count - len(specials))
                pool = (
                    ["Mafia"] * mafia_count + specials + ["Villager"] * villager_count
                )
                # Trim to exactly num_players if somehow over, or pad if under
                if len(pool) > self.num_players:
                    pool = pool[: self.num_players]
                while len(pool) < self.num_players:
                    pool.append("Villager")

                random.shuffle(pool)
                return " ".join(pool), None
            if self.phase in ["NIGHT_DOCTOR", "NIGHT_DETECTIVE", "NIGHT_VIGILANTE"]:
                return "skip", None

        if player_idx > 0:
            p_idx = player_idx - 1
            alive_targets = [i for i, a in enumerate(self.alive) if a]
            other_alive = [i for i in alive_targets if i != p_idx]

            if self.phase == "NIGHT_MAFIA_DISCUSSION":
                return "Let's take out someone quiet.", None

            if self.phase == "NIGHT_MAFIA_VOTE":
                target = random.choice(other_alive) if other_alive else p_idx
                return f"kill p{target + 1}", None

            if self.phase == "NIGHT_DOCTOR":
                allowed = [
                    t
                    for t in alive_targets
                    if getattr(self, "last_saved_player", None) != t
                ]
                if not allowed:
                    return "skip", None
                target = random.choice(allowed)
                return f"save p{target + 1}", None

            if self.phase == "NIGHT_DETECTIVE":
                target = random.choice(other_alive) if other_alive else p_idx
                return f"investigate p{target + 1}", None

            if self.phase == "NIGHT_VIGILANTE":
                return "skip", None

            if self.phase == "DAY_DISCUSSION":
                if not self.turn_question_asked and random.random() < 0.3:
                    target = random.choice(other_alive) if other_alive else p_idx
                    return f"p{target + 1}? Are you mafia?", None
                return "I am just a simple villager!", None

            if self.phase == "DAY_DISCUSSION_REPLY":
                return "I have no idea what you're talking about.", None

            if self.phase == "DAY_VOTE":
                if random.random() < 0.2:
                    return "vote none", None
                target = random.choice(other_alive) if other_alive else p_idx
                return f"vote p{target + 1}", None

        return None, "Invalid state for algorithm."
