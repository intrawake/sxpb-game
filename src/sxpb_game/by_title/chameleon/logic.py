import random
from typing import List, Optional, Tuple
from game_eval.logic import GameLogic, MoveResult


class ChameleonLogic(GameLogic):
    def __init__(self, num_players: int = 5):
        self.num_players = max(4, num_players - 1)
        self.phase = "SETUP_WORDS"
        self.words = []
        self.secret_word = None
        self.leader_idx = None
        self.chameleon_idx = None
        self.player_word_order = []
        self.player_word_idx = 0
        self.discussion_order = []
        self.discussion_idx = 0
        self.discussion_target = None
        self.turn_question_asked = False
        self.day_discussion_round = 0
        self.vote_order = []
        self.vote_idx = 0
        self.day_votes = {}
        self.tie_candidates = []
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
        if self.phase in [
            "SETUP_WORDS",
            "SETUP_SECRET",
            "SETUP_LEADER",
            "SETUP_CHAMELEON",
            "PLAYER_ORDER",
            "DAY_ORDER",
            "VOTE_ORDER",
        ]:
            return 0
        if self.phase == "PLAYER_WORDS":
            return (
                self.player_word_order[self.player_word_idx] + 1
                if self.player_word_idx < len(self.player_word_order)
                else None
            )
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
        if self.phase == "TIE_BREAK":
            return self.leader_idx + 1 if self.leader_idx is not None else None
        if self.phase == "CHAMELEON_GUESS":
            return self.chameleon_idx + 1 if self.chameleon_idx is not None else None
        return None

    def get_prompt(self, player_idx: int) -> str:
        if player_idx == 0:
            if self.phase == "SETUP_WORDS":
                return "Provide 16 words separated by spaces."
            if self.phase == "SETUP_SECRET":
                return "Pick the secret word from the 16 words."
            if self.phase == "SETUP_LEADER":
                return "Pick a leader (e.g. 'p1')."
            if self.phase == "SETUP_CHAMELEON":
                return "Pick a chameleon (e.g. 'p2')."
            if self.phase == "PLAYER_ORDER":
                return "Provide order for everyone to say a word (e.g. 'p1 p3 p4 p2')."
            if self.phase in ["DAY_ORDER", "VOTE_ORDER"]:
                if self.phase == "DAY_ORDER":
                    return "Provide order for discussion (all players)."
                return "Provide vote order (excluding the leader)."
        if self.phase == "PLAYER_WORDS":
            if player_idx - 1 == self.chameleon_idx:
                return "You are the chameleon! You do NOT know the secret word. Try to blend in by saying a related word based on what the others have said."
            return f"{'You are the leader. ' if player_idx - 1 == self.leader_idx else ''}The secret word is {self.secret_word}. Say a single word related to it to prove you know it, without making it too obvious for the Chameleon."
        if self.phase == "DAY_DISCUSSION":
            prompt = "Day discussion phase. "
            if not self.turn_question_asked:
                prompt += "You can ask one person a question by responding with `p<idx>? <question>`, OR "
            return (
                prompt
                + "Say something to the group, accuse someone, or defend yourself (this will end your turn)."
            )
        if self.phase == "DAY_DISCUSSION_REPLY":
            return "Someone asked you a direct question. Reply to them."
        if self.phase == "DAY_VOTE":
            return "Voting phase. Cast your vote for the chameleon (e.g. 'vote p2'). You cannot vote for the leader."
        if self.phase == "TIE_BREAK":
            opts = " or ".join([f"p{c + 1}" for c in self.tie_candidates])
            return f"There is a tie between {opts}. As leader, cast the tie-breaking vote (e.g. 'vote p2')."
        if self.phase == "CHAMELEON_GUESS":
            return "You have been caught! Guess the secret word to steal the win."
        return "Wait."

    def make_move(self, player_idx: int, move: str) -> MoveResult:
        if self.is_game_over() or player_idx != self.get_current_player():
            return MoveResult(False, "")
        parts = move.split()
        if not parts:
            return MoveResult(False, "")
        if player_idx == 0:
            if self.phase == "SETUP_WORDS":
                if len(parts) != 16:
                    return MoveResult(False, "")
                self.words = parts
                self.phase = "SETUP_SECRET"
                self.history.append("((event words_chosen))")
                return MoveResult(True, "")
            if self.phase == "SETUP_SECRET":
                if parts[0] not in self.words:
                    return MoveResult(False, "")
                self.secret_word = parts[0]
                self.phase = "SETUP_LEADER"
                self.history.append("((event secret_word_chosen))")
                return MoveResult(True, "")
            if self.phase == "SETUP_LEADER":
                if not parts[0].startswith("p"):
                    return MoveResult(False, "")
                try:
                    l_idx = int(parts[0][1:]) - 1
                    if 0 <= l_idx < self.num_players:
                        self.leader_idx = l_idx
                        self.phase = "SETUP_CHAMELEON"
                        self.history.append(
                            f"((event leader_chosen) (player p{l_idx + 1}))"
                        )
                        return MoveResult(True, "")
                except ValueError:
                    pass
                return MoveResult(False, "")
            if self.phase == "SETUP_CHAMELEON":
                if not parts[0].startswith("p"):
                    return MoveResult(False, "")
                try:
                    c_idx = int(parts[0][1:]) - 1
                    if 0 <= c_idx < self.num_players and c_idx != self.leader_idx:
                        self.chameleon_idx = c_idx
                        self.phase = "PLAYER_ORDER"
                        self.history.append("((event chameleon_chosen))")
                        return MoveResult(True, "")
                except ValueError:
                    pass
                return MoveResult(False, "")
            if self.phase in ["PLAYER_ORDER", "DAY_ORDER", "VOTE_ORDER"]:
                order = []
                for p in parts:
                    if p.startswith("p"):
                        try:
                            idx = int(p[1:]) - 1
                            if 0 <= idx < self.num_players and idx not in order:
                                if (
                                    self.phase == "VOTE_ORDER"
                                    and idx == self.leader_idx
                                ):
                                    continue
                                order.append(idx)
                        except ValueError:
                            pass
                for i in range(self.num_players):
                    if i not in order:
                        if self.phase == "VOTE_ORDER" and i == self.leader_idx:
                            continue
                        order.append(i)
                order_str = " ".join([f"p{i + 1}" for i in order])
                if self.phase == "PLAYER_ORDER":
                    self.player_word_order = order
                    self.player_word_idx = 0
                    self.phase = "PLAYER_WORDS"
                elif self.phase == "DAY_ORDER":
                    self.discussion_order = order
                    self.discussion_idx = 0
                    self.turn_question_asked = False
                    self.phase = "DAY_DISCUSSION"
                else:
                    self.vote_order = order
                    self.vote_idx = 0
                    self.day_votes = {}
                    self.phase = "DAY_VOTE"
                self.history.append(f"((event order_players) (()) {order_str})")
                return MoveResult(True, "")
        p_idx = player_idx - 1
        p_str = f"p{player_idx}"
        if self.phase in ["PLAYER_WORDS", "DAY_DISCUSSION", "DAY_DISCUSSION_REPLY"]:
            if (
                p_idx != self.chameleon_idx
                and self.secret_word
                and self.secret_word.lower() in move.lower()
            ):
                return MoveResult(
                    False,
                    "You cannot say the secret word! You are trying to hide it from the Chameleon.",
                )
        if self.phase == "PLAYER_WORDS":
            for word in self.words:
                if word.lower() in move.lower():
                    return MoveResult(
                        False,
                        f"You cannot say any of the candidate words (like '{word}') during the word-association phase!",
                    )
            self.history.append(f'({p_str} "{move}")')
            self.player_word_idx += 1
            if self.player_word_idx >= len(self.player_word_order):
                self.phase = "DAY_ORDER"
            return MoveResult(True, "")
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
                        if 0 <= target_idx < self.num_players and target_idx != p_idx:
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
            self.history.append(f'({p_str} "{move}")')
            self.discussion_idx += 1
            self.turn_question_asked = False
            if self.discussion_idx >= len(self.discussion_order):
                self.day_discussion_round += 1
                if self.day_discussion_round < 2:
                    self.phase = "DAY_ORDER"
                else:
                    self.phase = "VOTE_ORDER"
                    self.day_discussion_round = 0
            return MoveResult(True, "")
        if self.phase == "DAY_VOTE":
            if parts[0].lower() == "vote":
                if len(parts) < 2:
                    return MoveResult(False, "")
                target_str = parts[1]
                if not target_str.startswith("p"):
                    return MoveResult(False, "")
                try:
                    t_idx = int(target_str[1:]) - 1
                except ValueError:
                    return MoveResult(False, "")
                if t_idx < 0 or t_idx >= self.num_players or t_idx == self.leader_idx:
                    return MoveResult(False, "")
                self.day_votes[p_idx] = t_idx
                self.history.append(f"(vote {p_str} p{t_idx + 1})")
                self.vote_idx += 1
                if self.vote_idx >= len(self.vote_order):
                    self._resolve_vote()
                return MoveResult(True, "")
        if self.phase == "TIE_BREAK":
            if parts[0].lower() == "vote":
                if len(parts) < 2:
                    return MoveResult(False, "")
                target_str = parts[1]
                if not target_str.startswith("p"):
                    return MoveResult(False, "")
                try:
                    t_idx = int(target_str[1:]) - 1
                except ValueError:
                    return MoveResult(False, "")
                if t_idx not in self.tie_candidates:
                    return MoveResult(False, "")
                self.history.append(f"(vote {p_str} p{t_idx + 1}) ; tiebreaker")
                self._apply_vote_result(t_idx)
                return MoveResult(True, "")
        if self.phase == "CHAMELEON_GUESS":
            self.history.append(f'({p_str} "{move}")')
            if self.secret_word and move and self.secret_word.lower() in move.lower():
                self.game_over = True
                self.result = "Chameleon"
                self.history.append("((event game_over) (winning_team Chameleon))")
            else:
                self.game_over = True
                self.result = "Players"
                self.history.append("((event game_over) (winning_team Players))")
            return MoveResult(True, "")
        return MoveResult(False, "")

    def _resolve_vote(self):
        vote_counts = {}
        for v in self.day_votes.values():
            vote_counts[v] = vote_counts.get(v, 0) + 1
        if not vote_counts:
            self._apply_vote_result(None)
            return
        max_votes = max(vote_counts.values())
        candidates = [k for k, v in vote_counts.items() if v == max_votes]
        if len(candidates) > 1:
            self.tie_candidates = candidates
            self.phase = "TIE_BREAK"
            self.history.append("((event tie_break_needed))")
        else:
            self._apply_vote_result(candidates[0])

    def _apply_vote_result(self, voted_idx):
        if voted_idx == self.chameleon_idx:
            self.history.append(f"((event voted_chameleon) (player p{voted_idx + 1}))")
            self.phase = "CHAMELEON_GUESS"
        else:
            if voted_idx is not None:
                self.history.append(f"((event voted_wrong) (player p{voted_idx + 1}))")
            self.game_over = True
            self.result = "Chameleon"
            self.history.append("((event game_over) (winning_team Chameleon))")

    def render_player_history(self, player_idx: int) -> str:
        if not self.history:
            return "((history))"
        history_str = "\n ".join(self.history)
        return f"((history)\n {history_str}\n)"

    def render_player_view(self, player_idx: int) -> str:
        board = f"(table\n (phase {self.phase})\n"
        if hasattr(self, "words") and self.words:
            board += f" (words (()) {' '.join(self.words)})\n"
        if self.secret_word:
            if (
                player_idx == 0
                or self.is_game_over()
                or (player_idx > 0 and player_idx - 1 != self.chameleon_idx)
            ):
                board += f" (secret_word {self.secret_word})\n"
        if self.phase in ["DAY_DISCUSSION", "DAY_DISCUSSION_REPLY"]:
            rem = self.discussion_order[self.discussion_idx :]
            if rem:
                board += (
                    f" (discussion_queue (()) {' '.join([f'p{i + 1}' for i in rem])})\n"
                )
        board += " (players ()\n"
        for i in range(self.num_players):
            board += f"  (p{i + 1}"
            if i == self.leader_idx:
                board += " (role Leader)"
            else:
                is_cham = i == self.chameleon_idx
                knows = (
                    player_idx == 0
                    or self.is_game_over()
                    or player_idx - 1 == self.chameleon_idx
                )
                if is_cham and knows:
                    board += " (role Chameleon)"
                elif knows and not is_cham:
                    board += " (role Player)"
            board += ")\n"
        return board + " )\n)\n"

    def get_rules(self) -> str:
        return (
            "Chameleon is a social deduction word game.\n"
            "The GM picks 16 words, and one of them is the secret word.\n"
            "One player is the Leader, and one player is the Chameleon.\n"
            "Everyone except the Chameleon knows the secret word.\n"
            "The Leader says a word related to the secret word, followed by the rest of the players.\n"
            "The Chameleon must blend in and say a word without knowing the secret word.\n"
            "Then, everyone discusses for 2 rounds and votes on who the Chameleon is.\n"
            "The Leader does not vote, but breaks ties.\n"
            "If the Chameleon escapes the vote, they win. If caught, they can still win by guessing the secret word."
        )

    def get_algorithm_move(
        self, player_idx: int, algorithm: str
    ) -> Tuple[Optional[str], Optional[str]]:
        if algorithm != "random":
            return super().get_algorithm_move(player_idx, algorithm)
        if player_idx == 0:
            if self.phase == "SETUP_WORDS":
                return (
                    "apple banana cherry date elderberry fig grape honeydew kiwi lemon mango nectarine orange papaya quince raspberry",
                    None,
                )
            if self.phase == "SETUP_SECRET":
                return random.choice(self.words) if self.words else "apple", None
            if self.phase == "SETUP_LEADER":
                return f"p{random.randint(1, self.num_players)}", None
            if self.phase == "SETUP_CHAMELEON":
                opts = [i for i in range(self.num_players) if i != self.leader_idx]
                return f"p{random.choice(opts) + 1}", None
            if self.phase == "PLAYER_ORDER":
                opts = [
                    f"p{i + 1}" for i in range(self.num_players) if i != self.leader_idx
                ]
                random.shuffle(opts)
                return f"p{(self.leader_idx or 0) + 1} " + " ".join(opts), None
            if self.phase in ["DAY_ORDER", "VOTE_ORDER"]:
                opts = [
                    f"p{i + 1}"
                    for i in range(self.num_players)
                    if i != (self.leader_idx if self.phase == "VOTE_ORDER" else -1)
                ]
                random.shuffle(opts)
                return " ".join(opts), None
        if player_idx > 0:
            if self.phase == "PLAYER_WORDS":
                return "fruit", None
            if self.phase == "DAY_DISCUSSION":
                return "I think it's p2.", None
            if self.phase == "DAY_DISCUSSION_REPLY":
                return "No, I am not the chameleon.", None
            if self.phase == "DAY_VOTE":
                opts = [i for i in range(self.num_players) if i != self.leader_idx]
                return f"vote p{random.choice(opts) + 1}", None
            if self.phase == "TIE_BREAK":
                return f"vote p{random.choice(self.tie_candidates) + 1}", None
            if self.phase == "CHAMELEON_GUESS":
                return "apple", None
        return None, "Invalid state for algorithm."
