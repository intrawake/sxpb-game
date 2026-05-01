import os
import sys
import random
import re
from typing import List, Optional

# Ensure we can import from src
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))
from sxpb_game.eval.logic import GameLogic, MoveResult


class ConnectFourLogic(GameLogic):
    ROWS = 6
    COLS = 7
    COL_LABELS = ["a", "b", "c", "d", "e", "f", "g"]

    def __init__(self):
        self.board = [[" " for _ in range(self.COLS)] for _ in range(self.ROWS)]
        self.heights = [0] * self.COLS
        self.history = []
        self.current_player = "R"
        self.winner = None
        self.move_count = 0

    def is_valid_col(self, col_idx):
        return 0 <= col_idx < self.COLS and self.heights[col_idx] < self.ROWS

    def get_valid_moves(self):
        return [
            self.COL_LABELS[c] for c in range(self.COLS) if self.heights[c] < self.ROWS
        ]

    def parse_move(self, move_str):
        if not move_str:
            return None
        clean = move_str.strip().upper()
        match = re.search(r"([RY])?\s*([A-G])([1-6])?", clean)
        if not match:
            return None
        col_char = match.group(2).lower()
        col_idx = self.COL_LABELS.index(col_char)
        if not self.is_valid_col(col_idx):
            return None
        return col_idx

    def undo_move(self, col):
        if self.heights[col] == 0:
            return False
        self.heights[col] -= 1
        row = self.ROWS - 1 - self.heights[col]
        self.board[row][col] = " "
        self.history.pop()
        self.move_count -= 1
        self.winner = None
        self.current_player = "Y" if self.current_player == "R" else "R"
        return True

    def check_winner(self, r, c):
        player = self.board[r][c]
        directions = [(0, 1), (1, 0), (1, -1), (1, 1)]
        for dr, dc in directions:
            count = 1
            for i in range(1, 4):
                nr, nc = r + dr * i, c + dc * i
                if (
                    0 <= nr < self.ROWS
                    and 0 <= nc < self.COLS
                    and self.board[nr][nc] == player
                ):
                    count += 1
                else:
                    break
            for i in range(1, 4):
                nr, nc = r - dr * i, c - dc * i
                if (
                    0 <= nr < self.ROWS
                    and 0 <= nc < self.COLS
                    and self.board[nr][nc] == player
                ):
                    count += 1
                else:
                    break
            if count >= 4:
                return True
        return False

    def get_player_identifiers(self) -> List[str]:
        return ["R", "Y"]

    def is_game_over(self) -> bool:
        return self.winner is not None

    def get_current_player(self) -> Optional[int]:
        if self.is_game_over():
            return None
        return 0 if self.current_player == "R" else 1

    def get_prompt(self, player_idx: int) -> str:
        player_id = self.get_player_identifiers()[player_idx]
        player_full = (
            "RED" if player_id == "R" else "YELLOW" if player_id == "Y" else player_id
        )
        return f"What is your move for player {player_full}?"

    def make_move(self, player_idx: int, move: str) -> MoveResult:
        col_idx_or_str = move
        if self.is_game_over() or self.get_current_player() != player_idx:
            return MoveResult(False, "")

        if isinstance(col_idx_or_str, str):
            col = self.parse_move(col_idx_or_str)
            if col is None:
                return MoveResult(False, "")
        else:
            col = col_idx_or_str

        if not self.is_valid_col(col):
            return MoveResult(False, "")

        row = self.ROWS - 1 - self.heights[col]
        move_str = f"{self.current_player}{self.COL_LABELS[col]}{self.ROWS - row}"
        self.board[row][col] = self.current_player
        self.heights[col] += 1
        self.history.append(move_str)
        self.move_count += 1

        if self.check_winner(row, col):
            self.winner = self.current_player
        elif self.move_count == self.ROWS * self.COLS:
            self.winner = "Draw"

        self.current_player = "Y" if self.current_player == "R" else "R"
        return MoveResult(True, "")

    def __str__(self):
        idx = 0 if self.current_player == "R" else 1
        return self.render_player_view(idx)

    def render_player_history(self, player_idx: int) -> str:
        moves_str = "\n " + " ".join(self.history) + "\n" if self.history else "\n"
        return f"; --- Move History (Algebraic Notation) ---\n(moves (()){moves_str})"

    def render_player_view(self, player_idx: int) -> str:
        def get_row_list(r_idx):
            return [(c if c != " " else "_") for c in self.board[r_idx]]

        row6 = " ".join(get_row_list(0))
        row5 = " ".join(get_row_list(1))
        row4 = " ".join(get_row_list(2))
        row3 = " ".join(get_row_list(3))
        row2 = " ".join(get_row_list(4))
        row1 = " ".join(get_row_list(5))

        player_full = "RED" if self.current_player == "R" else "YELLOW"
        return f"""\
; --- Connect Four (7 Columns x 6 Rows) ---
(board
 ; Columns: a b c d e f g
 (row6 (()) {row6})
 (row5 (()) {row5})
 (row4 (()) {row4})
 (row3 (()) {row3})
 (row2 (()) {row2})
 (row1 (()) {row1})
 ; Columns: a b c d e f g
)

; --- Game Metadata ---
(player_to_move {player_full})
(move_count {self.move_count})"""

    def get_algorithm_move(
        self, player_idx: int, algorithm: str
    ) -> tuple[Optional[str], Optional[str]]:
        if algorithm != "random":
            return super().get_algorithm_move(player_idx, algorithm)

        valid_moves = self.get_valid_moves()
        if not valid_moves:
            return None, "No valid moves available."

        return random.choice(valid_moves), None
