import os
import sys
from typing import List, Optional

# Ensure we can import from src
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))
from game_eval.logic import GameLogic, MoveResult


class MastermindLogic(GameLogic):
    def __init__(self, target_code: Optional[str] = None):
        self.target_code = target_code.upper().replace(" ", "") if target_code else None
        self.colors = ["R", "G", "B", "Y", "O", "P"]
        self.code_len = 4
        self.max_turns = 10
        self.rows = []
        self.turn_count = 0
        self.last_guess = None
        self.winner = None

    def get_player_identifiers(self) -> List[str]:
        return ["0", "1"]

    def is_game_over(self) -> bool:
        if self.target_code is None:
            return False
        if self.last_guess == self.target_code:
            if not self.winner:
                self.winner = "1"
            return True
        if self.turn_count >= self.max_turns:
            if not self.winner:
                self.winner = "0"
            return True
        return False

    def get_current_player(self) -> Optional[int]:
        if self.is_game_over():
            return None
        if self.target_code is None:
            return 0
        return 1

    def get_prompt(self, player_idx: int) -> str:
        colors_str = ", ".join(self.colors)
        if player_idx == 0:
            return f"What is your secret 4-color code? Colors: {colors_str}."
        return f"What is your next guess? Colors: {colors_str}."

    def calculate_feedback(self, guess: str) -> tuple[int, int]:
        guess_list = list(guess)
        secret_list = list(self.target_code or "")
        exact = sum(g == s for g, s in zip(guess_list, secret_list))
        secret_remain = [s for g, s in zip(guess_list, secret_list) if g != s]
        guess_remain = [g for g, s in zip(guess_list, secret_list) if g != s]
        color_match = sum(
            min(guess_remain.count(c), secret_remain.count(c))
            for c in set(guess_remain)
        )
        return exact, color_match

    def get_valid_moves(self) -> List[str]:
        return [
            f"A {self.code_len}-character string using colors: {', '.join(self.colors)}"
        ]

    def make_move(self, player_idx: int, move: str) -> MoveResult:
        guess = move
        if self.is_game_over():
            return MoveResult(False, "")

        guess = guess.upper().replace(" ", "")

        if player_idx == 0:
            if self.target_code is not None:
                return MoveResult(False, "")
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
