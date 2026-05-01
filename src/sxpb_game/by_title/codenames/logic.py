import sys
import os
import random
from typing import List, Optional

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))
from sxpb_game.eval.logic import GameLogic, MoveResult


class CodenamesLogic(GameLogic):
    def __init__(self):
        super().__init__()

        # Load words from wordlist.txt
        wordlist_path = os.path.join(os.path.dirname(__file__), "wordlist.sxpb")
        with open(wordlist_path, "r", encoding="utf-8") as f:
            full_word_list = []
            for line in f:
                w = line.strip()
                if w and w != "(())":
                    # Remove quotes if present
                    if w.startswith('"') and w.endswith('"'):
                        w = w[1:-1]
                    full_word_list.append(w.upper())

        self.words = random.sample(full_word_list, 25)

        # Red goes first: 9 Red, 8 Blue, 1 Assassin, 7 Neutral
        colors_pool = ["red"] * 9 + ["blue"] * 8 + ["assassin"] + ["neutral"] * 7
        random.shuffle(colors_pool)
        self.word_colors = {word: color for word, color in zip(self.words, colors_pool)}

        self.revealed = set()

        # 0: Dealer, 1: Red Spymaster, 2: Blue Spymaster, 3: Red Operative, 4: Blue Operative
        self.players = [
            "Dealer",
            "Red_Spymaster",
            "Blue_Spymaster",
            "Red_Operative",
            "Blue_Operative",
        ]

        self.current_player_idx = 1  # Red Spymaster goes first
        self.guesses_left = 0
        self.winner = None
        self.history = []

    def get_player_identifiers(self) -> List[str]:
        return self.players

    def is_game_over(self) -> bool:
        return self.winner is not None

    def get_current_player(self) -> Optional[int]:
        if self.is_game_over():
            return None
        return self.current_player_idx

    def get_prompt(self, player_idx: int) -> str:
        if player_idx in [1, 2]:
            return "Give a clue formatted as 'WORD NUMBER' (e.g. 'OCEAN 2')."
        elif player_idx in [3, 4]:
            return f"Guess exactly ONE word from the table, or type '.' to stop guessing. You have up to {self.guesses_left} guesses left."
        return "Wait for your turn."

    def make_move(self, player_idx: int, move: str) -> MoveResult:
        if self.is_game_over() or self.get_current_player() != player_idx:
            return MoveResult(False, "")

        move = move.strip().upper()

        if player_idx in [1, 2]:
            # Spymaster turn
            parts = move.split()
            if len(parts) != 2:
                return MoveResult(False, "")
            clue_word, clue_num_str = parts[0], parts[1]

            # The clue cannot be a word currently visible on the table
            unrevealed_words = {w for w in self.words if w not in self.revealed}
            if clue_word in unrevealed_words:
                return MoveResult(False, "")

            try:
                clue_num = int(clue_num_str)
            except ValueError:
                return MoveResult(False, "")
            if clue_num < 0:
                return MoveResult(False, "")

            # Switch to corresponding operative
            self.guesses_left = clue_num + 1
            self.history.append(f'(p{player_idx} "{clue_word} {clue_num}")')
            self.current_player_idx = 3 if player_idx == 1 else 4
            return MoveResult(True, "")

        elif player_idx in [3, 4]:
            # Operative turn
            team = "red" if player_idx == 3 else "blue"
            other_team = "blue" if team == "red" else "red"
            next_spymaster_idx = 2 if player_idx == 3 else 1

            # If the LLM hallucinated extra text (like guessing "CHINA 2" instead of "CHINA"),
            # we just take the first word as their guess to make parsing more robust.
            move = move.split()[0] if move else ""

            if move == ".":
                self.history.append(f'(p{player_idx} ".")')
                self.current_player_idx = next_spymaster_idx
                return MoveResult(True, "")

            if move not in self.words or move in self.revealed:
                return MoveResult(False, "")

            self.revealed.add(move)
            color = self.word_colors[move]

            if " " in move:
                self.history.append(f'(p{player_idx} "{move}")')
            else:
                self.history.append(f"(p{player_idx} {move})")
            self.history.append(f"(reveal {color})")

            if color == "assassin":
                self.winner = other_team
                return MoveResult(True, "")

            if color == team:
                self.guesses_left -= 1
                if self.check_win(team):
                    self.winner = team
                elif self.guesses_left <= 0:
                    self.current_player_idx = next_spymaster_idx
            else:
                # Guessed wrong team or neutral
                if color == other_team and self.check_win(other_team):
                    self.winner = other_team
                else:
                    self.current_player_idx = next_spymaster_idx

            return MoveResult(True, "")

        return MoveResult(False, "")

    def check_win(self, team: str) -> bool:
        total = 9 if team == "red" else 8
        found = sum(
            1 for w in self.words if self.word_colors[w] == team and w in self.revealed
        )
        return found == total

    def render_player_history(self, player_idx: int) -> str:
        if self.history:
            h_lines = []
            cur_line = []
            for h in self.history:
                if h.startswith("(p1 ") or h.startswith("(p2 "):
                    if cur_line:
                        h_lines.append(" ".join(cur_line))
                        cur_line = []
                cur_line.append(h)
            if cur_line:
                h_lines.append(" ".join(cur_line))
            history_str = "\n  ".join(h_lines)
            return f"((history)\n  {history_str}\n)"
        else:
            return "((history))"

    def render_player_view(self, player_idx: int) -> str:
        score_red = sum(
            1 for w in self.words if self.word_colors[w] == "red" and w in self.revealed
        )
        score_blue = sum(
            1
            for w in self.words
            if self.word_colors[w] == "blue" and w in self.revealed
        )

        score_block = f"(score\n (red {score_red})\n (blue {score_blue})\n)"

        if player_idx in [0, 1, 2]:
            # Spymaster / Dealer view
            red_words = [
                w
                for w in self.words
                if self.word_colors[w] == "red" and w not in self.revealed
            ]
            blue_words = [
                w
                for w in self.words
                if self.word_colors[w] == "blue" and w not in self.revealed
            ]
            neutral_words = [
                w
                for w in self.words
                if self.word_colors[w] == "neutral" and w not in self.revealed
            ]
            assassin_word = [
                w
                for w in self.words
                if self.word_colors[w] == "assassin" and w not in self.revealed
            ]

            def fmt_list(lst):
                return " ".join(f'"{w}"' if " " in w else w for w in lst) if lst else ""

            ass_str = (
                f"\n (assassin {fmt_list(assassin_word)})" if assassin_word else ""
            )

            table_block = f"(table\n (red (()) {fmt_list(red_words)})\n (blue (()) {fmt_list(blue_words)}){ass_str}\n (neutral (()) {fmt_list(neutral_words)})\n)"
            return f"{table_block}\n\n{score_block}"
        else:
            # Operative view
            unrevealed = [w for w in self.words if w not in self.revealed]
            words_str = " ".join(f'"{w}"' if " " in w else w for w in unrevealed)
            table_block = f"(table\n (words (()) {words_str})\n)"
            return f"{table_block}\n\n{score_block}"

    def get_algorithm_move(
        self, player_idx: int, algorithm: str
    ) -> tuple[Optional[str], Optional[str]]:
        if algorithm != "random":
            return super().get_algorithm_move(player_idx, algorithm)

        if player_idx in [1, 2]:
            return "HINT 1", None
        elif player_idx in [3, 4]:
            unrevealed = [w for w in self.words if w not in self.revealed]
            if unrevealed:
                return random.choice(unrevealed), None
            return ".", None
        return None, "Not your turn."
