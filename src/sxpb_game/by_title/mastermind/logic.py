import random
from typing import List, Optional, Tuple
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from sxpb_game.eval.logic import GameLogic, MoveResult, read_rulebook


class MastermindLogic(GameLogic):
    def __init__(self, target_code: Optional[str] = None):
        self.colors = ["R", "G", "B", "Y", "O", "P"]
        self.code_len = 4
        self.max_turns = 10
        self.target_code = target_code
        self.rows = []
        self.turn_count = 0
        self.game_over = False
        self.result = None
        self.last_guess = None

    def get_player_identifiers(self) -> List[str]:
        return ["0", "1"]

    def get_outcome_player_indices(self) -> List[int]:
        return [1]

    def get_visible_players(self, player_idx: int) -> List[int]:
        return [1]

    @property
    def winner(self) -> Optional[str]:
        if not self.game_over:
            return None
        return self.result

    def is_game_over(self) -> bool:
        if self.game_over:
            return True
        if self.rows and self.rows[-1][0] == self.target_code:
            self.game_over = True
            self.result = "1"
            return True
        if self.turn_count >= self.max_turns:
            self.game_over = True
            self.result = "0"
            return True
        return False

    def get_current_player(self) -> Optional[int]:
        if self.is_game_over():
            return None
        if self.target_code is None:
            return 0
        return 1

    def get_prompt(self, player_idx: int) -> str:
        if player_idx == 0:
            if self.target_code is None:
                return (
                    "Choose a 4-color secret code using R, G, B, Y, O, P (e.g. 'RGBY')."
                )
            return "Wait."
        if player_idx == 1:
            if self.target_code is None:
                return "Wait for the secret code to be chosen."
            return f"Enter your 4-color guess (attempt {self.turn_count + 1}/{self.max_turns})."
        return "Wait."

    def calculate_feedback(self, guess: str) -> Tuple[int, int]:
        assert self.target_code is not None
        target: List[Optional[str]] = list(self.target_code)
        guess_list: List[Optional[str]] = list(guess)
        exact = 0
        partial = 0

        # Find exact matches
        for i in range(self.code_len):
            if guess_list[i] == target[i]:
                exact += 1
                target[i] = None
                guess_list[i] = None

        # Find partial matches
        for i in range(self.code_len):
            if guess_list[i] is not None and guess_list[i] in target:
                partial += 1
                target[target.index(guess_list[i])] = None

        return exact, partial

    def make_move(self, player_idx: int, move: str) -> MoveResult:
        if self.is_game_over() or player_idx != self.get_current_player():
            return MoveResult(False, "Not your turn.")

        guess = move.upper().strip()
        if player_idx == 0:
            if len(guess) != self.code_len or not all(c in self.colors for c in guess):
                return MoveResult(False, "")
            self.target_code = guess
            return MoveResult(True, "")

        if player_idx != 1 or self.target_code is None:
            return MoveResult(False, "")

        if len(guess) != self.code_len or not all(c in self.colors for c in guess):
            return MoveResult(False, "")

        exact, partial = self.calculate_feedback(guess)
        self.rows.append((guess, (exact, partial)))
        self.turn_count += 1
        self.last_guess = guess
        self.is_game_over()  # update winner
        return MoveResult(True, "")

    def render_player_view(self, player_idx: int) -> str:
        lines = []
        lines.append("; --- Mastermind ---")
        if player_idx == 0:
            if self.target_code:
                lines.append(f"; The secret code is: {self.target_code}")
            else:
                lines.append("; You need to choose a 4-color secret code.")
        else:
            if self.is_game_over() and self.target_code:
                lines.append(
                    f"; The game is over. The secret code was: {self.target_code}"
                )

        lines.append("(board")
        for i in range(self.max_turns):
            row_num = i + 1
            if i < len(self.rows):
                g, (e, p) = self.rows[i]
                guess_str = " ".join(list(g))
                lines.append(
                    f" (row{row_num} (()) {guess_str}) (clue{row_num} (()) {e} {p})"
                )
            else:
                lines.append(f" (row{row_num} (()) _ _ _ _)")
        lines.append(")")

        lines.append("")
        lines.append("; --- Game Metadata ---")
        lines.append(f"(colors (()) {' '.join(self.colors)})")
        lines.append(f"(turn_count {self.turn_count})")
        return "\n".join(lines)

    def get_rules(self) -> str:
        return read_rulebook(__file__)

    def get_valid_moves(self) -> List[str]:
        if self.is_game_over():
            return []
        if self.get_current_player() == 0:
            return ["any 4 colors (e.g. RGBY)"]
        return ["any 4 colors (e.g. RGBY)"]

    def get_algorithm_move(
        self, player_idx: int, algorithm: str
    ) -> Tuple[Optional[str], Optional[str]]:
        if algorithm != "random":
            return super().get_algorithm_move(player_idx, algorithm)

        # Simple random choice from available colors
        code = "".join(random.choices(self.colors, k=self.code_len))
        return code, None
