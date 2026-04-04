import sys
import os
import random
from typing import List, Optional

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))
from game_eval.logic import GameLogic, MoveResult


class TicTacToeLogic(GameLogic):
    def __init__(self):
        self.board = {(c, r): None for c in range(3) for r in range(3)}
        self.history = []
        self.current_player = "X"
        self.winner = None
        self.move_count = 0
        self.col_map = {0: "a", 1: "b", 2: "c"}
        self.row_map = {0: "1", 1: "2", 2: "3"}
        self.inv_col = {"a": 0, "b": 1, "c": 2}
        self.inv_row = {"1": 0, "2": 1, "3": 2}

    def parse_move(self, move_str):
        if not move_str:
            return None
        clean = move_str.strip().lower()
        if len(clean) == 3 and clean[0] in ["x", "o"]:
            clean = clean[1:]
        if len(clean) != 2:
            return None
        c_char = clean[0]
        r_char = clean[1]
        if c_char not in self.inv_col or r_char not in self.inv_row:
            return None
        return (self.inv_col[c_char], self.inv_row[r_char])

    def format_move(self, col, row, with_player=False):
        m = f"{self.col_map[col]}{self.row_map[row]}"
        return f"{self.current_player}{m}" if with_player else m

    def check_winner(self):
        lines = (
            [[(c, 0), (c, 1), (c, 2)] for c in range(3)]
            + [[(0, r), (1, r), (2, r)] for r in range(3)]
            + [[(0, 0), (1, 1), (2, 2)], [(0, 2), (1, 1), (2, 0)]]
        )
        for line in lines:
            vals = [self.board[pos] for pos in line]
            if vals[0] and vals[0] == vals[1] == vals[2]:
                self.winner = vals[0]
                return
        if all(v is not None for v in self.board.values()):
            self.winner = "Draw"

    def get_valid_moves(self):
        moves = []
        for c in range(3):
            for r in range(3):
                if self.board[(c, r)] is None:
                    moves.append(self.format_move(c, r))
        return moves

    def get_player_identifiers(self) -> List[str]:
        return ["X", "O"]

    def is_game_over(self) -> bool:
        return self.winner is not None

    def get_current_player(self) -> Optional[int]:
        if self.is_game_over():
            return None
        return 0 if self.current_player == "X" else 1

    def get_prompt(self, player_idx: int) -> str:
        player_id = self.get_player_identifiers()[player_idx]
        return f"What is your move for player {player_id}?"

    def make_move(self, player_idx: int, move: str) -> MoveResult:
        move_str = move
        if self.is_game_over() or self.get_current_player() != player_idx:
            return MoveResult(False, "")

        coords = self.parse_move(move_str)
        if not coords:
            return MoveResult(False, "")
        col, row = coords
        if self.board[(col, row)] is not None:
            return MoveResult(False, "")

        self.board[(col, row)] = self.current_player
        self.history.append(self.format_move(col, row, with_player=True))
        self.move_count += 1
        self.check_winner()
        self.current_player = "O" if self.current_player == "X" else "X"
        return MoveResult(True, "")

    def render_player_history(self, player_idx: int) -> str:
        moves = " ".join(self.history)
        moves_section = f"\n {moves}\n" if moves else "\n"
        return f"; --- Move History ---\n(moves (()){moves_section})"

    def render_player_view(self, player_idx: int) -> str:
        def get_row(r):
            return [self.board[(c, r)] if self.board[(c, r)] else "_" for c in range(3)]

        row3 = " ".join(get_row(2))
        row2 = " ".join(get_row(1))
        row1 = " ".join(get_row(0))

        return f"""\
; --- Tic-Tac-Toe (3 Columns x 3 Rows) ---
(board
 ; Columns: a b c
 (row3 (()) {row3})
 (row2 (()) {row2})
 (row1 (()) {row1})
 ; Columns: a b c
)

; --- Game Metadata ---
(player_to_move {self.current_player})
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
