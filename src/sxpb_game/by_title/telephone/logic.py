import random
from typing import List, Optional, Tuple
from sxpb_game.eval.logic import GameLogic, MoveResult, read_rulebook


class TelephoneLogic(GameLogic):
    def __init__(self, num_players: int = 3):
        # We need at least p0 (Source), p1 (Judge), p2 (Player 2)
        self.num_players = max(3, num_players)
        self.phase = "CHOOSE_QUIRKS"
        self.quirks = {}
        self.messages = {}
        self.current_quirk_idx = 1
        self.current_player_idx = 1
        self.game_over = False
        self.result = None
        self.history = []

    def get_player_identifiers(self) -> List[str]:
        return ["Source", "Judge"] + [f"p{i}" for i in range(2, self.num_players)]

    def get_outcome_player_indices(self) -> List[int]:
        return list(range(1, self.num_players))

    def get_visible_players(self, player_idx: int) -> List[int]:
        return self.get_outcome_player_indices()

    @property
    def winner(self) -> Optional[str]:
        return self.result if self.game_over else None

    def is_game_over(self) -> bool:
        return self.game_over

    def get_current_player(self) -> Optional[int]:
        if self.is_game_over():
            return None
        if self.phase == "CHOOSE_QUIRKS":
            return self.current_quirk_idx
        if self.phase == "CHOOSE_MESSAGE":
            return 0
        if self.phase == "PASS_MESSAGE":
            return self.current_player_idx
        if self.phase == "JUDGE":
            return 1
        return None

    def get_prompt(self, player_idx: int) -> str:
        if self.phase == "CHOOSE_QUIRKS" and player_idx == self.current_quirk_idx:
            if player_idx == 1:
                return "You are the Judge, but you also play! Choose a unique speaking style or quirk for yourself. Use format: 'quirk <description>'"
            return "Choose a unique speaking style or quirk for yourself. Use format: 'quirk <description>'"
        if self.phase == "CHOOSE_MESSAGE" and player_idx == 0:
            return (
                "You are the Source. Write the initial message for the telephone game."
            )
        if self.phase == "PASS_MESSAGE" and player_idx == self.current_player_idx:
            quirk = self.quirks.get(player_idx, "None")
            prev_player = player_idx - 1
            if prev_player == 0:
                prev_msg = self.messages[0]
                return f"The Source passed you a message: '{prev_msg}'. Your chosen quirk is: {quirk}. Pass the message to the next player using your quirk."
            else:
                prev_msg = self.messages[prev_player]
                return f"Player p{prev_player} passed you a message: '{prev_msg}'. Your chosen quirk is: {quirk}. Pass the message to the next player using your quirk."
        if self.phase == "JUDGE" and player_idx == 1:
            return "You are the Judge. Pick a winner based on how well a message is preserved and the roleplay. Output your verdict as 'winner pN <reason>' on the same line."
        return "Wait."

    def make_move(self, player_idx: int, move: str) -> MoveResult:
        if self.is_game_over() or player_idx != self.get_current_player():
            return MoveResult(False, "")

        move = move.strip()
        if not move:
            return MoveResult(False, "")

        if self.phase == "CHOOSE_QUIRKS":
            if move.startswith("quirk "):
                parts = move.split(maxsplit=1)
                if len(parts) < 2:
                    return MoveResult(False, "Format: quirk <description>")
                self.quirks[player_idx] = parts[1]
                self.history.append(f'(quirk p{player_idx} "{parts[1]}")')
                self.current_quirk_idx += 1
                if self.current_quirk_idx >= self.num_players:
                    self.phase = "CHOOSE_MESSAGE"
                return MoveResult(True, "")
            return MoveResult(False, "Format: quirk <description>")

        if self.phase == "CHOOSE_MESSAGE":
            self.messages[0] = move
            self.history.append(f'(p0 "{move}")')
            self.current_player_idx = 1
            self.phase = "PASS_MESSAGE"
            return MoveResult(True, "")

        if self.phase == "PASS_MESSAGE":
            self.messages[self.current_player_idx] = move
            self.history.append(f'(p{self.current_player_idx} "{move}")')
            self.current_player_idx += 1
            if self.current_player_idx >= self.num_players:
                self.phase = "JUDGE"
            return MoveResult(True, "")

        if self.phase == "JUDGE":
            if not move.lower().startswith("winner p"):
                return MoveResult(False, "Format: winner pN <reason>")
            self.history.append(f'(judge_verdict "{move}")')
            self.game_over = True
            parts = move.split(maxsplit=2)
            if len(parts) >= 2 and parts[1].lower().startswith("p"):
                self.result = parts[1].lower()
            else:
                self.result = "Completed"
            return MoveResult(True, "")

        return MoveResult(False, "")

    def render_player_history(self, player_idx: int) -> str:
        visible_history = []
        for h in self.history:
            if h.startswith("(judge_verdict "):
                visible_history.append(h)
            elif h.startswith("(p"):
                parts = h.split(" ", 1)
                if len(parts) >= 2:
                    try:
                        msg_p_idx = int(parts[0][2:])
                    except ValueError:
                        continue

                    if player_idx == 0:
                        visible_history.append(h)
                    elif player_idx == 1 and (
                        self.phase == "JUDGE" or self.is_game_over()
                    ):
                        visible_history.append(h)
                    elif player_idx == msg_p_idx:
                        visible_history.append(h)
                    elif player_idx == msg_p_idx + 1:
                        visible_history.append(h)

        if not visible_history:
            return "((history))"
        history_str = "\n ".join(visible_history)
        return f"((history)\n {history_str}\n)"

    def render_player_view(self, player_idx: int) -> str:
        board = f"(table\n (phase {self.phase})\n"
        if self.quirks:
            board += " (quirk_by_player\n"
            for p, q in sorted(self.quirks.items()):
                board += f'  (p{p} "{q}")\n'
            board += " )\n"
        if self.phase == "CHOOSE_QUIRKS":
            board += f" (current_turn p{self.current_quirk_idx})\n"
        if self.phase == "PASS_MESSAGE":
            board += f" (current_turn p{self.current_player_idx})\n"
        board += ")\n"
        return board

    def get_rules(self) -> str:
        return read_rulebook(__file__)

    def get_algorithm_move(
        self, player_idx: int, algorithm: str
    ) -> Tuple[Optional[str], Optional[str]]:
        if algorithm != "random":
            return super().get_algorithm_move(player_idx, algorithm)

        if self.phase == "CHOOSE_QUIRKS" and player_idx == self.current_quirk_idx:
            quirk_pool = ["speaks like a pirate", "speaks like a caveman"]
            return f"quirk {random.choice(quirk_pool)}", None
        if player_idx == 0 and self.phase == "CHOOSE_MESSAGE":
            return "The quick brown fox jumps over the lazy dog.", None
        if self.phase == "PASS_MESSAGE" and player_idx == self.current_player_idx:
            return "Yarrr, the fast brown fox leaps o'er the sleepy hound, matey!", None
        if player_idx == 1 and self.phase == "JUDGE":
            opts = [f"p{i}" for i in range(1, self.num_players)]
            return f"winner {random.choice(opts)} you all did great!", None

        return None, "Invalid state for algorithm."
