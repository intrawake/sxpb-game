import string
import os
import sys
from typing import List, Optional

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from game_eval.logic import GameLogic, MoveResult, read_rulebook


class TwentyQuestionsLogic(GameLogic):
    def __init__(self):
        self.secret_word = None
        self.history = []  # List of tuples: (question, answer)
        self.phase = "choose_word"  # "choose_word", "ask_question", "answer_question", "game_over"
        self.winner = None
        self.questions_asked = 0
        self.max_questions = 20
        self.current_question = None

    def get_player_identifiers(self) -> List[str]:
        return ["Oracle", "Guesser"]

    def get_rules(self) -> str:
        return read_rulebook(__file__)

    def is_game_over(self) -> bool:
        return self.phase == "game_over"

    def get_current_player(self) -> Optional[int]:
        if self.is_game_over():
            return None
        if self.phase == "choose_word" or self.phase == "answer_question":
            return 0
        return 1

    def get_prompt(self, player_idx: int) -> str:
        if player_idx == 0:
            if self.phase == "choose_word":
                return "Choose a secret word for the Guesser to guess."
            elif self.phase == "answer_question":
                return f"The Guesser asked: '{self.current_question}'."
        elif player_idx == 1:
            return f"Ask question {self.questions_asked + 1} of {self.max_questions} (or guess the word)."
        return ""

    def get_valid_moves(self) -> List[str]:
        if self.phase == "answer_question":
            return ["yes", "no", "somewhat", "usually", "rarely", "idk"]
        return []

    def _strip_punct(self, text: str) -> str:
        return text.translate(str.maketrans("", "", string.punctuation)).strip().lower()

    def make_move(self, player_idx: int, move: str) -> MoveResult:
        if self.is_game_over() or self.get_current_player() != player_idx:
            return MoveResult(False, "Not your turn or game is over.")

        move = move.strip()
        if not move:
            return MoveResult(False, "Move cannot be empty.")

        if self.phase == "choose_word" and player_idx == 0:
            cleaned = self._strip_punct(move)
            words = cleaned.split()
            if not words:
                return MoveResult(False, "Invalid secret word.")
            self.secret_word = words[-1]
            self.phase = "ask_question"
            return MoveResult(True, "")

        elif self.phase == "ask_question" and player_idx == 1:
            cleaned = self._strip_punct(move)
            words = cleaned.split()
            if not words:
                return MoveResult(False, "Invalid question.")

            self.questions_asked += 1
            self.current_question = move

            if words[-1] == self.secret_word:
                self.winner = 1
                self.phase = "game_over"
                self.history.append((move, "[Guessed correctly!]"))
                return MoveResult(True, "")

            self.phase = "answer_question"
            return MoveResult(True, "")

        elif self.phase == "answer_question" and player_idx == 0:
            cleaned = self._strip_punct(move)
            if (
                "yes" in cleaned
                or "yep" in cleaned
                or "yeah" in cleaned
                or "y" == cleaned
            ):
                answer = "yes"
            elif "no" in cleaned or "nope" in cleaned or "n" == cleaned:
                answer = "no"
            elif "usually" in cleaned:
                answer = "usually"
            elif "rarely" in cleaned:
                answer = "rarely"
            elif (
                "idk" in cleaned
                or "don't know" in move.lower()
                or "dont know" in move.lower()
                or "not sure" in move.lower()
            ):
                answer = "idk"
                self.questions_asked -= 1
            else:
                return MoveResult(
                    False, "You must answer 'yes', 'no', 'usually', 'rarely', or 'idk'."
                )

            self.history.append((self.current_question, answer))
            self.current_question = None

            if self.questions_asked >= self.max_questions:
                self.winner = 0
                self.phase = "game_over"
            else:
                self.phase = "ask_question"
            return MoveResult(True, "")

        return MoveResult(False, "Invalid state.")

    def render_player_history(self, player_idx: int) -> str:
        if not self.history:
            return ""

        lines = []
        for i, (q, a) in enumerate(self.history):
            # User wants: (p1 "Is it a vehicle?") (p0 no)
            # The prompt requested:
            # ((history)
            #  (p1 "Is it a vehicle?") (p0 no)
            #  ;...
            # )
            # We'll format the values depending on spaces. Or just quote the question.
            q_escaped = q.replace('"', '\\"')
            a_escaped = a.replace('"', '\\"')
            if " " in a_escaped:
                lines.append(f' (p1 "{q_escaped}") (p0 "{a_escaped}")')
            else:
                lines.append(f' (p1 "{q_escaped}") (p0 {a_escaped})')

        history_str = "\n".join(lines)
        return f"; --- Q&A History ---\n((history)\n{history_str}\n)"

    def render_player_view(self, player_idx: int) -> str:
        lines = []
        lines.append("; --- Twenty Questions ---")
        lines.append(f"(max_questions {self.max_questions})")
        lines.append(f"(questions_asked {self.questions_asked})")

        if player_idx == 0 and self.secret_word:
            lines.append(f"(secret_word {self.secret_word})")

        if self.phase == "answer_question" and self.current_question:
            # Just print the literal string since it might have spaces
            lines.append(f"(pending_question {self.current_question})")

        if self.is_game_over() and self.winner is not None:
            winner_name = self.get_player_identifiers()[self.winner]
            lines.append(f"(winner {winner_name})")

        return "\n".join(lines)
