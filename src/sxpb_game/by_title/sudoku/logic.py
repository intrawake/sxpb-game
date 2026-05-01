import os
import sys
import re
import random
from typing import List, Optional, Tuple

# Ensure we can import from src
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))
from sxpb_game.eval.logic import GameLogic, MoveResult


class SudokuLogic(GameLogic):
    def __init__(self, board_input=None):
        # 9x9 grid, 0 represents empty cell
        self.grid = [[0 for _ in range(9)] for _ in range(9)]
        self.fixed = [[False for _ in range(9)] for _ in range(9)]
        self.board_initialized = False

        if board_input:
            self._load_board(board_input)
            self.board_initialized = True

    def _load_board(self, board_input):
        # Flattened list of numbers/dots
        # Can be string or file path
        if os.path.exists(board_input):
            with open(board_input, "r") as f:
                content = f.read()
        else:
            content = board_input

        # Extract rows from SxPB format if possible, otherwise just find all tokens
        if "(row" in content:
            for r in range(9):
                row_idx = 9 - r  # row9 to row1
                match = re.search(rf"\(row{row_idx}\s+([^)]+)\)", content)
                if match:
                    tokens = match.group(1).split()
                    token_idx = 0
                    for c in range(9):
                        if token_idx < len(tokens):
                            token = tokens[token_idx]
                            if token.isdigit():
                                self.grid[r][c] = int(token)
                                self.fixed[r][c] = True
                            else:
                                self.grid[r][c] = 0
                            token_idx += 1
        else:
            # Fallback: just find 81 characters
            tokens = content.replace(".", "0").split()
            if len(tokens) == 1 and len(tokens[0]) == 81:
                tokens = list(tokens[0])
            idx = 0
            for r in range(9):
                for c in range(9):
                    if idx < len(tokens):
                        val = tokens[idx]
                        if val.isdigit() and val != "0":
                            self.grid[r][c] = int(val)
                            self.fixed[r][c] = True
                        idx += 1

    def is_valid_move(self, row, col, val):
        if not (0 <= row < 9 and 0 <= col < 9 and 1 <= val <= 9):
            return False
        if self.fixed[row][col]:
            return False

        # Check row
        if val in self.grid[row]:
            return False

        # Check column
        if val in [self.grid[r][col] for r in range(9)]:
            return False

        # Check 3x3 box
        start_row, start_col = 3 * (row // 3), 3 * (col // 3)
        for r in range(start_row, start_row + 3):
            for c in range(start_col, start_col + 3):
                if self.grid[r][c] == val:
                    return False
        return True

    def get_player_identifiers(self) -> List[str]:
        return ["GM", "Player"]

    def is_game_over(self) -> bool:
        if not self.board_initialized:
            return False
        for r in range(9):
            for c in range(9):
                if self.grid[r][c] == 0:
                    return False
        return True

    def get_current_player(self) -> Optional[int]:
        if self.is_game_over():
            return None
        if not self.board_initialized:
            return 0
        return 1

    def get_prompt(self, player_idx: int) -> str:
        if player_idx == 0:
            return "Please provide the initial Sudoku board."
        return "What is your next move?"

    def make_move(self, player_idx: int, move: str) -> MoveResult:
        move_str = move
        if self.is_game_over() or player_idx != self.get_current_player():
            return MoveResult(False, "")

        if player_idx == 0:
            # GM sets up the board
            self._load_board(move_str)
            self.board_initialized = True
            return MoveResult(True, "")

        # Format: "a9=5", "Move: a9=5", or "5 at a9"
        match = re.search(r"([a-i])([1-9])\s*=\s*([1-9])", move_str, re.IGNORECASE)
        if match:
            col = ord(match.group(1).lower()) - ord("a")
            row = 9 - int(match.group(2))
            val = int(match.group(3))
        else:
            match = re.search(r"([1-9])\s+at\s+([a-i])([1-9])", move_str, re.IGNORECASE)
            if match:
                val = int(match.group(1))
                col = ord(match.group(2).lower()) - ord("a")
                row = 9 - int(match.group(3))
            else:
                return MoveResult(False, "")

        if self.is_valid_move(row, col, val):
            self.grid[row][col] = val
            return MoveResult(True, "")
        return MoveResult(False, "")

    def render_player_view(self, player_idx: int) -> str:
        lines = []
        lines.append("; --- Sudoku (9x9 Grid) ---")
        lines.append('(board ("")')
        lines.append(" ; Col  a b c  d e f  g h i")
        for r in range(9):
            row_num = 9 - r
            row_vals = []
            for c in range(9):
                val = self.grid[r][c]
                row_vals.append(str(val) if val != 0 else ".")
                if c in [2, 5]:  # Add spacers for visual clarity
                    row_vals.append(" ")

            lines.append(f" (row{row_num}  {' '.join(row_vals)})")
            if r in [2, 5]:  # Blank line between boxes
                lines.append("")
        lines.append(")")
        return "\n".join(lines)

    def _generate_solved_board(self):
        def is_valid_for_gen(grid, r, c, val):
            for i in range(9):
                if grid[r][i] == val or grid[i][c] == val:
                    return False
            sr, sc = 3 * (r // 3), 3 * (c // 3)
            for i in range(sr, sr + 3):
                for j in range(sc, sc + 3):
                    if grid[i][j] == val:
                        return False
            return True

        def solve(grid):
            for r in range(9):
                for c in range(9):
                    if grid[r][c] == 0:
                        nums = list(range(1, 10))
                        random.shuffle(nums)
                        for n in nums:
                            if is_valid_for_gen(grid, r, c, n):
                                grid[r][c] = n
                                if solve(grid):
                                    return True
                                grid[r][c] = 0
                        return False
            return True

        grid = [[0] * 9 for _ in range(9)]
        solve(grid)
        return grid

    def get_algorithm_move(
        self, player_idx: int, algorithm: str
    ) -> Tuple[Optional[str], Optional[str]]:
        if algorithm != "random":
            return super().get_algorithm_move(player_idx, algorithm)

        if player_idx == 0:
            grid = self._generate_solved_board()
            cells = [(r, c) for r in range(9) for c in range(9)]
            random.shuffle(cells)
            # Remove 45-55 cells for a playable game
            num_holes = random.randint(45, 55)
            for r, c in cells[:num_holes]:
                grid[r][c] = 0

            res = []
            for r in range(9):
                for c in range(9):
                    res.append(str(grid[r][c]) if grid[r][c] != 0 else ".")
            return "".join(res), None

        if player_idx == 1:
            # Player 1 random move (not really smart, but picks a valid random move)
            valid_moves = []
            for r in range(9):
                for c in range(9):
                    if self.grid[r][c] == 0:
                        for v in range(1, 10):
                            if self.is_valid_move(r, c, v):
                                valid_moves.append(f"{chr(c + ord('a'))}{9 - r}={v}")
            if not valid_moves:
                return None, "No valid moves available."
            return random.choice(valid_moves), None

        return None, "Invalid player index."
