import os
import sys
from typing import List, Optional

# Ensure we can import from src
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))
from sxpb_game.eval.logic import GameLogic, MoveResult


class WordleLogic(GameLogic):
    def __init__(self, target_word: Optional[str] = None):
        self.target_word = target_word.upper() if target_word else None
        self.board = {f"guess{i + 1}": ["_", "_", "_", "_", "_"] for i in range(6)}
        self.pinned = ["_", "_", "_", "_", "_"]
        self.present = []
        self.absent = []
        self.guess_count = 0
        self.last_guess = None
        self.winner = None

    def get_player_identifiers(self) -> List[str]:
        return ["0", "1"]

    def get_outcome_player_indices(self) -> List[int]:
        return [1]

    def is_game_over(self) -> bool:
        if self.target_word is None:
            return False
        if self.last_guess == self.target_word:
            if not self.winner:
                self.winner = "1"
            return True
        if self.guess_count >= 6:
            if not self.winner:
                self.winner = "0"
            return True
        return False

    def get_current_player(self) -> Optional[int]:
        if self.is_game_over():
            return None
        if self.target_word is None:
            return 0
        return 1

    def get_prompt(self, player_idx: int) -> str:
        if player_idx == 0:
            return "What is your 5-letter secret word?"
        return "What is your 5-letter word guess?"

    def get_feedback(self, guess: str) -> List[str]:
        temp_target: List[Optional[str]] = list(self.target_word or "")
        temp_guess: List[Optional[str]] = list(guess.upper())
        status = [0] * 5  # 0: Unknown, 1: Pinned, 2: Present, 3: Absent

        for i in range(5):
            if temp_guess[i] == temp_target[i]:
                status[i] = 1
                temp_target[i] = None
                temp_guess[i] = None

        for i in range(5):
            if temp_guess[i] is not None:
                if temp_guess[i] in temp_target:
                    status[i] = 2
                    temp_target[temp_target.index(temp_guess[i])] = None
                else:
                    status[i] = 3

        final_display = []
        real_guess_upper = guess.upper()
        for i in range(5):
            char = real_guess_upper[i]
            if status[i] == 1 or status[i] == 2:
                final_display.append(char.upper())
            else:
                final_display.append(char.lower())
        return final_display

    def get_valid_moves(self) -> List[str]:
        return ["Any 5-letter English word"]

    def make_move(self, player_idx: int, move: str) -> MoveResult:
        guess = move
        if self.is_game_over():
            return MoveResult(False, "")

        if player_idx == 0:
            if self.target_word is not None:
                return MoveResult(False, "")
            word = guess.upper()
            if len(word) != 5 or not word.isalpha():
                return MoveResult(False, "")
            self.target_word = word
            return MoveResult(True, "")

        if player_idx != 1 or self.target_word is None:
            return MoveResult(False, "")

        guess = guess.upper()
        if len(guess) != 5 or not guess.isalpha():
            return MoveResult(False, "")

        feedback = self.get_feedback(guess)
        self.guess_count += 1
        self.board[f"guess{self.guess_count}"] = feedback
        self.last_guess = guess

        target_chars = list(self.target_word)
        guess_chars = list(guess)

        for i in range(5):
            g_char = guess_chars[i]
            t_char = target_chars[i]

            if g_char == t_char:
                self.pinned[i] = g_char
                if g_char not in self.present:
                    self.present.append(g_char)
                if g_char in self.absent:
                    self.absent.remove(g_char)
            elif g_char in self.target_word:
                if g_char not in self.present:
                    self.present.append(g_char)
                if g_char in self.absent:
                    self.absent.remove(g_char)
            else:
                if g_char not in self.present and g_char not in self.absent:
                    self.absent.append(g_char)

        self.is_game_over()  # update winner
        return MoveResult(True, "")

    def render_player_view(self, player_idx: int) -> str:
        lines = []
        lines.append("; --- Wordle ---")
        if player_idx == 0:
            if self.target_word:
                lines.append(f"; The secret word is: {self.target_word}")
            else:
                lines.append("; You need to choose a 5-letter secret word.")
        else:
            if self.is_game_over() and self.target_word:
                lines.append(
                    f"; The game is over. The secret word was: {self.target_word}"
                )

        lines.append("(board")

        for i in range(1, 7):
            guess = self.board[f"guess{i}"]
            lines.append(f" (guess{i} (()) {' '.join(guess)})")

        lines.append(" ; Letters guessed in correct positions.")
        lines.append(f" (pinned (()) {' '.join(self.pinned)})")
        lines.append(")")
        lines.append("")
        lines.append("; --- Game Metadata ---")

        present = sorted(list(set(self.present)))
        absent = sorted(list(set(self.absent)))

        lines.append(f"(present (()) {' '.join(present)})")
        lines.append(f"(absent (()) {' '.join(absent)})")
        lines.append(f"(guess_count {self.guess_count})")

        return "\n".join(lines)
