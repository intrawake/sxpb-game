import os
import sys
import re
import random
from typing import List, Optional, Tuple

# Add shared src to path
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))
from game_eval.logic import GameLogic, MoveResult


class MinesweeperLogic(GameLogic):
    def __init__(self, mine_input="10"):
        self.width = 8
        self.height = 8
        self.mines = set()
        self.revealed = set()
        self.flags = set()
        self.questions = set()
        self.game_over = False
        self.winner = None
        self.hit_mine = False

        self.fixed_mine_set = None
        self.target_mine_count = 10

        if mine_input.isdigit():
            self.target_mine_count = int(mine_input)
        else:
            self.fixed_mine_set = set()
            for m in mine_input.split():
                coords = self._parse_coords(m)
                if coords:
                    self.fixed_mine_set.add(coords)
            self.target_mine_count = len(self.fixed_mine_set)

        self.initialized = False
        self.mines_placed = False
        self.first_move = None

    def get_player_identifiers(self) -> List[str]:
        return ["GM", "Player"]

    def is_game_over(self) -> bool:
        return self.game_over

    def get_current_player(self) -> Optional[int]:
        if self.is_game_over():
            return None
        if not self.mines_placed and self.first_move is not None:
            return 0
        return 1

    def get_prompt(self, player_idx: int) -> str:
        if player_idx == 0:
            if self.first_move:
                c = chr(self.first_move[0] + ord("a"))
                r = self.first_move[1] + 1
                return f"Player has moved at {c}{r}. Please provide {self.target_mine_count} mine locations."
            return f"Please provide {self.target_mine_count} mine locations."
        return "What is your next move? (You can provide multiple moves separated by spaces, e.g., 'Oa1 Fb2 ?c3')"

    def _parse_coords(self, s):
        s = s.strip().lower()
        if len(s) < 2:
            return None
        col = ord(s[0]) - ord("a")
        try:
            row = int(s[1:]) - 1
        except ValueError:
            return None
        if 0 <= col < self.width and 0 <= row < self.height:
            return (col, row)
        return None

    def _get_neighbors(self, col, row):
        neighbors = []
        for dc in [-1, 0, 1]:
            for dr in [-1, 0, 1]:
                if dc == 0 and dr == 0:
                    continue
                nc, nr = col + dc, row + dr
                if 0 <= nc < self.width and 0 <= nr < self.height:
                    neighbors.append((nc, nr))
        return neighbors

    def _count_neighbor_mines(self, col, row):
        count = 0
        for nc, nr in self._get_neighbors(col, row):
            if (nc, nr) in self.mines:
                count += 1
        return count

    def _reveal(self, col, row):
        if (col, row) in self.revealed:
            return
        self.revealed.add((col, row))
        if self._count_neighbor_mines(col, row) == 0:
            for nc, nr in self._get_neighbors(col, row):
                if (nc, nr) not in self.mines:
                    self._reveal(nc, nr)

    def make_move(self, player_idx: int, move: str) -> MoveResult:
        move_str = move
        if self.is_game_over() or player_idx != self.get_current_player():
            return MoveResult(False, "")

        if player_idx == 0:
            mines = move_str.strip().split()
            parsed_mines = set()
            for m in mines:
                c = self._parse_coords(m)
                if c:
                    parsed_mines.add(c)
            self.mines = parsed_mines
            self.mines_placed = True
            self.initialized = True

            if self.first_move:
                fc, fr = self.first_move
                if self.first_move in self.mines:
                    self.hit_mine = True
                    self.game_over = True
                    self.winner = "GM"
                else:
                    self._reveal(fc, fr)
                    if len(self.revealed) + len(self.mines) == self.width * self.height:
                        self.game_over = True
                        self.winner = "Player"
            return MoveResult(True, "")

        tokens = move_str.strip().split()
        if not tokens:
            return MoveResult(False, "")

        if not self.mines_placed:
            if len(tokens) != 1:
                return MoveResult(False, "")
            match = re.match(r"^([O])([a-h][1-8])$", tokens[0], re.IGNORECASE)
            if not match:
                return MoveResult(False, "")
            action = match.group(1).upper()
            coords = self._parse_coords(match.group(2))
            if not coords or action != "O":
                return MoveResult(False, "")
            self.first_move = coords
            return MoveResult(True, "")

        any_success = False
        for token in tokens:
            if self.game_over:
                break
            match = re.match(r"^([OF\?U])([a-h][1-8])$", token, re.IGNORECASE)
            if not match:
                continue

            action = match.group(1).upper()
            coords = self._parse_coords(match.group(2))
            if not coords:
                continue
            col, row = coords

            if action == "O":
                if coords in self.flags:
                    continue
                if coords in self.revealed:
                    continue
                if coords in self.mines:
                    self.hit_mine = True
                    self.game_over = True
                    self.winner = "GM"
                    any_success = True
                    break
                self._reveal(col, row)
                if len(self.revealed) + len(self.mines) == self.width * self.height:
                    self.game_over = True
                    self.winner = "Player"
                any_success = True
            elif action == "F":
                if coords not in self.revealed:
                    self.flags.add(coords)
                    self.questions.discard(coords)
                    any_success = True
            elif action == "?":
                if coords not in self.revealed:
                    self.questions.add(coords)
                    self.flags.discard(coords)
                    any_success = True
            elif action == "U":
                if coords in self.flags or coords in self.questions:
                    self.flags.discard(coords)
                    self.questions.discard(coords)
                    any_success = True

        return MoveResult(any_success, "")

    def render_player_view(self, player_idx: int) -> str:
        lines = []
        lines.append("; --- Minesweeper (8x8 Beginner) ---")
        lines.append('(board ("")')
        lines.append(" ; COL a b c d e f g h")
        for r in range(self.height - 1, -1, -1):
            row_cells = []
            for c in range(self.width):
                coords = (c, r)
                if coords in self.flags:
                    row_cells.append("F")
                elif coords in self.questions:
                    row_cells.append("?")
                elif not self.initialized:
                    row_cells.append("_")
                elif coords in self.revealed:
                    row_cells.append(str(self._count_neighbor_mines(c, r)))
                elif self.game_over and coords in self.mines and player_idx == 1:
                    row_cells.append("*")
                elif player_idx == 0 and coords in self.mines:
                    row_cells.append("*")
                else:
                    row_cells.append("_")
            lines.append(f" (row{r + 1} {' '.join(row_cells)})")
        lines.append(")")

        if player_idx == 1 and self.game_over:
            lines.append("")
            mine_locations = [
                f"{chr(c + ord('a'))}{r + 1}"
                for c, r in sorted(self.mines, key=lambda x: (x[1], x[0]))
            ]
            lines.append(
                f"; The game is over. Mine locations were: {' '.join(mine_locations)}"
            )
        lines.append("")
        lines.append("; --- Game Metadata ---")
        m_count = len(self.mines) if self.initialized else self.target_mine_count
        lines.append(f"(total_mines {m_count})")
        lines.append(f"(flags_placed {len(self.flags)})")
        state_str = "in_progress"
        if self.hit_mine:
            state_str = "lost"
        elif self.game_over:
            state_str = "won"
        lines.append(f"(state {state_str})")
        return "\n".join(lines)

    def get_rules(self) -> str:
        return (
            "Minesweeper is a grid puzzle game where the objective is to clear a board containing hidden mines without detonating any of them.\n"
            "Numbers on revealed squares indicate how many mines are adjacent to that square (including diagonally).\n"
            "You can provide multiple moves in a single turn by separating them with spaces (e.g., 'Oa1 Fb2 ?c3').\n"
            "Valid actions for a coordinate (e.g., 'a1'):\n"
            "- 'Oa1': Open (reveal) the square at a1.\n"
            "- 'Fa1': Place a flag on a1 to mark a suspected mine.\n"
            "- '?a1': Place a question mark on a1.\n"
            "- 'Ua1': Remove a flag or question mark from the square at a1."
        )

    def get_algorithm_move(
        self, player_idx: int, algorithm: str
    ) -> Tuple[Optional[str], Optional[str]]:
        if algorithm != "random":
            return super().get_algorithm_move(player_idx, algorithm)

        if player_idx == 0:
            if not self.first_move:
                return None, "Player 1 has not made the first move yet."
            first_col, first_row = self.first_move
            forbidden = set(self._get_neighbors(first_col, first_row))
            forbidden.add((first_col, first_row))

            all_cells = [(c, r) for c in range(self.width) for r in range(self.height)]
            possible_cells = [c for c in all_cells if c not in forbidden]

            count = min(self.target_mine_count, len(possible_cells))
            chosen = random.sample(possible_cells, count)

            move_parts = []
            for c, r in chosen:
                move_parts.append(f"{chr(c + ord('a'))}{r + 1}")
            return " ".join(move_parts), None

        # Player 1 random move
        if player_idx == 1:
            if not self.mines_placed:
                # Need to make first move
                all_cells = [
                    (c, r) for c in range(self.width) for r in range(self.height)
                ]
                c, r = random.choice(all_cells)
                return f"O{chr(c + ord('a'))}{r + 1}", None
            else:
                unrevealed = []
                for c in range(self.width):
                    for r in range(self.height):
                        if (c, r) not in self.revealed and (c, r) not in self.flags:
                            unrevealed.append((c, r))
                if not unrevealed:
                    return None, "No valid moves available."
                c, r = random.choice(unrevealed)
                return f"O{chr(c + ord('a'))}{r + 1}", None

        return None, "Invalid player index."
