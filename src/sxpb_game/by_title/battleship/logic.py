import random
import os
import re
import sys
from typing import List, Optional, Tuple

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))
from sxpb_game.eval.logic import GameLogic, MoveResult, read_rulebook


class BattleshipLogic(GameLogic):
    def __init__(self):
        self.grid_size = 10
        self.ship_types = [
            ("carrier", 5),
            ("battleship", 4),
            ("cruiser", 3),
            ("submarine", 3),
            ("destroyer", 2),
        ]
        # boards[p] stores ship names at (col, row)
        self.boards = [{} for _ in range(2)]
        # shots[p] stores hits/misses fired BY player p AT opponent
        self.shots_fired = [{} for _ in range(2)]
        # ships[p][name] = list of (col, row)
        self.ships = [{} for _ in range(2)]
        # sunk_ships[p] = list of names
        self.sunk_ships = [[] for _ in range(2)]
        # placed_ships[p] = set of ship names placed by player p
        self.placed_ships = [set() for _ in range(2)]

        self.phase = "PLACEMENT"
        self.current_player_idx = 0

        self.history = []
        self.winner = None

        self.col_map = {i: chr(ord("a") + i) for i in range(10)}
        self.inv_col = {v: k for k, v in self.col_map.items()}

    def get_player_identifiers(self) -> List[str]:
        return ["p1", "p2"]

    def get_rules(self) -> str:
        return read_rulebook(__file__)

    def is_game_over(self) -> bool:
        return self.winner is not None

    def get_current_player(self) -> Optional[int]:
        if self.is_game_over():
            return None
        return self.current_player_idx

    def get_valid_moves(self) -> List[str]:
        if self.phase == "PLACEMENT":
            remaining = [
                f"{name}({length})"
                for name, length in self.ship_types
                if name not in self.placed_ships[self.current_player_idx]
            ]
            if remaining:
                return [
                    "place <ship> <coord> <h/v>",
                    f"Remaining: {', '.join(remaining)}",
                ]
            return ["place <ship> <coord> <h/v>"]
        else:
            remaining = len(self.ship_types) - len(
                self.sunk_ships[self.current_player_idx]
            )
            return [
                f"fire <coord1> <coord2> ... [. optional message] — {remaining} shots (Salvo Mode)"
            ]

    def parse_coord(self, s: str) -> Optional[Tuple[int, int]]:
        s = s.strip().lower()
        if not s or len(s) < 2:
            return None
        col_char = s[0]
        if col_char not in self.inv_col:
            return None
        try:
            row = int(s[1:]) - 1
            if not (0 <= row < self.grid_size):
                return None
            return (self.inv_col[col_char], row)
        except ValueError:
            return None

    def format_coord(self, col: int, row: int) -> str:
        return f"{self.col_map[col]}{row + 1}"

    def get_prompt(self, player_idx: int) -> str:
        if self.phase == "PLACEMENT":
            remaining = [
                f"{name}({length})"
                for name, length in self.ship_types
                if name not in self.placed_ships[player_idx]
            ]
            if remaining:
                return f"Place one of your remaining ships: {', '.join(remaining)}. Format: place <ship> <coord> <h/v>"
            return "Place your ships. Format: place <ship> <coord> <h/v>"
        else:
            ships_remaining = len(self.ship_types) - len(self.sunk_ships[player_idx])
            return f"It is your turn to attack. You have {ships_remaining} shots (Salvo Mode). Format: fire <coord1> <coord2> ... [. optional message]"

    def make_move(self, player_idx: int, move) -> MoveResult:
        if self.is_game_over() or player_idx != self.current_player_idx:
            return MoveResult(False, "Not your turn.")

        if not move:
            return MoveResult(False, "No move provided.")

        # Capture original move string for history
        if isinstance(move, str):
            original_move = move.strip()
        elif isinstance(move, dict):
            # Dict form: reconstruct from parsed
            parts = []
            for cmd, args in move.items():
                if isinstance(args, list):
                    parts.append(f"{cmd} {' '.join(args)}")
                else:
                    parts.append(f"{cmd} {args}" if args else cmd)
            original_move = " ".join(parts)
        else:
            original_move = str(move)

        # If it's already a dict, it came from parsed SxPB
        if isinstance(move, dict):
            parsed = move
        else:
            # Treat as bare string command: "cmd arg1 arg2 ..."
            # This handles (answer "fire a1 b2") where "fire a1 b2" is passed here.
            move_str = str(move).strip()
            parts = move_str.split(maxsplit=1)
            if not parts:
                return MoveResult(False, "Empty move string.")
            cmd = parts[0].lower()
            args_str = parts[1] if len(parts) > 1 else ""
            parsed = {cmd: args_str}

        if self.phase == "PLACEMENT":
            return self._handle_placement(player_idx, parsed, original_move)
        else:
            return self._handle_attack(player_idx, parsed, original_move)

    def _handle_placement(
        self, player_idx: int, parsed: dict, original_move: str
    ) -> MoveResult:
        if "place" not in parsed:
            return MoveResult(False, "Expected: place <ship> <coord> <h/v>")

        args = parsed["place"]
        if isinstance(args, str):
            args = args.split()

        if not isinstance(args, list) or len(args) < 3:
            return MoveResult(False, f"Invalid place arguments: {args}")

        ship_name = args[0].lower()
        coord_str = args[1]
        orientation = args[2].lower()

        # Validate ship type
        ship_entry = next((s for s in self.ship_types if s[0] == ship_name), None)
        if ship_entry is None:
            return MoveResult(
                False,
                f"Unknown ship: {ship_name}. Valid: {', '.join(s[0] for s in self.ship_types)}",
            )
        ship_name, ship_len = ship_entry

        # Validate not already placed
        if ship_name in self.placed_ships[player_idx]:
            return MoveResult(False, f"You already placed your {ship_name}.")

        coords = self.parse_coord(coord_str)
        if not coords:
            return MoveResult(False, f"Invalid coordinate: {coord_str}")

        col, row = coords
        ship_coords = []
        for i in range(ship_len):
            if orientation == "h":
                c, r = col + i, row
            elif orientation == "v":
                c, r = col, row + i
            else:
                return MoveResult(False, "Orientation must be 'h' or 'v'.")

            if not (0 <= c < self.grid_size and 0 <= r < self.grid_size):
                return MoveResult(False, "Ship goes out of bounds.")
            if (c, r) in self.boards[player_idx]:
                return MoveResult(False, "Ship overlaps with another ship.")
            ship_coords.append((c, r))

        # Place ship
        for c, r in ship_coords:
            self.boards[player_idx][(c, r)] = ship_name
        self.ships[player_idx][ship_name] = ship_coords
        self.placed_ships[player_idx].add(ship_name)

        self.history.append(f"p{player_idx + 1} {original_move}")

        # Advance state: p1 places all ships, then p2 places all ships.
        if len(self.placed_ships[player_idx]) == len(self.ship_types):
            if player_idx == 0:
                self.current_player_idx = 1
            else:
                self.phase = "ATTACK"
                self.current_player_idx = 0

        return MoveResult(True, "")

    def _handle_attack(
        self, player_idx: int, parsed: dict, original_move: str
    ) -> MoveResult:
        if "fire" not in parsed:
            return MoveResult(False, "Expected: fire <coord1> <coord2> ...")

        shots_args = parsed["fire"]
        if isinstance(shots_args, str):
            # Extract coordinate tokens, discarding trailing message text.
            # Coordinates are a-j followed by 1-10, optionally with trailing punctuation.
            coord_re = re.compile(r"^[a-j](?:[1-9]|10)$", re.IGNORECASE)
            tokens = shots_args.split()

            def _is_coord(t):
                return bool(coord_re.match(t.rstrip(".,;:!?")))

            shots_args = [t.rstrip(".,;:!?") for t in tokens if _is_coord(t)]
        elif not isinstance(shots_args, list):
            # Single atom shot (fire a1)
            shots_args = [shots_args]

        ships_remaining = len(self.ship_types) - len(self.sunk_ships[player_idx])
        if len(shots_args) != ships_remaining:
            return MoveResult(
                False,
                f"You must fire exactly {ships_remaining} shots (one for each remaining ship).",
            )

        shot_coords = []
        for s in shots_args:
            c = self.parse_coord(s)
            if not c:
                return MoveResult(False, f"Invalid shot coordinate: {s}")
            if c in self.shots_fired[player_idx]:
                return MoveResult(False, f"You already fired at {s}.")
            if c in shot_coords:
                return MoveResult(False, f"Duplicate shot coordinate in this turn: {s}")
            shot_coords.append(c)

        opponent_idx = 1 - player_idx
        results = []
        for c in shot_coords:
            if c in self.boards[opponent_idx]:
                ship_name = self.boards[opponent_idx][c]
                self.shots_fired[player_idx][c] = "hit"
                # Check for sink
                ship_all_coords = self.ships[opponent_idx][ship_name]
                if all(pos in self.shots_fired[player_idx] for pos in ship_all_coords):
                    self.sunk_ships[opponent_idx].append(ship_name)
                    results.append(f"{self.format_coord(*c)}: HIT (SUNK {ship_name}!)")
                else:
                    results.append(f"{self.format_coord(*c)}: HIT")
            else:
                self.shots_fired[player_idx][c] = "miss"
                results.append(f"{self.format_coord(*c)}: MISS")

        self.history.append(f"p{player_idx + 1} {original_move}")

        # Check game over
        if len(self.sunk_ships[opponent_idx]) == len(self.ship_types):
            self.winner = self.get_player_identifiers()[player_idx]
        else:
            self.current_player_idx = opponent_idx

        return MoveResult(True, "")

    def render_player_history(self, player_idx: int) -> str:
        lines = []
        for h in self.history:
            # Format: "p1 place carrier a1 h" or "p1 fire a1 b2 ..."
            for p in range(1, 3):
                prefix = f"p{p} "
                if h.startswith(prefix):
                    move_str = h[len(prefix) :]
                    if move_str.startswith("place"):
                        if p == player_idx + 1 or self.is_game_over():
                            # Own placement or game over: show full move
                            lines.append(f'(p{p} "{move_str}")')
                        else:
                            # Opponent placement: redact coordinates
                            parts = move_str.split()
                            ship_name = parts[1] if len(parts) > 1 else "unknown"
                            lines.append(f'(p{p} "place {ship_name} [redacted]")')
                    else:
                        # Fire or other move: show as-is
                        lines.append(f'(p{p} "{move_str}")')
                    break
        return (
            "; --- Move History ---\n"
            + "((history)\n"
            + "\n".join(f" {line}" for line in lines)
            + "\n)"
        )

    def render_player_view(self, player_idx: int) -> str:
        opponent_idx = 1 - player_idx

        ship_abbrev = {
            "carrier": "A",
            "battleship": "B",
            "cruiser": "C",
            "submarine": "S",
            "destroyer": "D",
        }

        def get_own_cell(c, r):
            ship = self.boards[player_idx].get((c, r))
            shot = self.shots_fired[opponent_idx].get((c, r))
            if shot == "hit":
                return "X"
            if shot == "miss":
                return "o"
            return ship_abbrev.get(ship, ".") if ship else "."

        def get_opponent_cell(c, r):
            shot = self.shots_fired[player_idx].get((c, r))
            if shot == "hit":
                return "X"
            if shot == "miss":
                return "o"
            if self.is_game_over():
                ship = self.boards[opponent_idx].get((c, r))
                return ship_abbrev.get(ship, ".") if ship else "."
            return "."

        own_board = []
        opp_board = []
        for r in range(self.grid_size - 1, -1, -1):
            own_row = " ".join(get_own_cell(c, r) for c in range(10))
            own_board.append(f" (row{r + 1:02} {own_row})")
            opp_row = " ".join(get_opponent_cell(c, r) for c in range(10))
            opp_board.append(f" (row{r + 1:02} {opp_row})")

        own_board_str = "\n".join(own_board)
        opp_board_str = "\n".join(opp_board)

        ships_left = [
            s[0] for s in self.ship_types if s[0] not in self.sunk_ships[player_idx]
        ]
        opp_ships = [
            s[0] for s in self.ship_types if s[0] not in self.sunk_ships[opponent_idx]
        ]

        return f"""\
; --- BATTLESHIP ---
(phase {self.phase})

; Ally Board (X=hit, o=miss, Letter=Ship, .=water)
(ally_board ("")
 ; Col: a b c d e f g h i j
{own_board_str}
 ; Col: a b c d e f g h i j
)

; Opponent's Board (X=hit, o=miss, .=unknown)
(opponent_board ("")
 ; Col: a b c d e f g h i j
{opp_board_str}
 ; Col: a b c d e f g h i j
)

(ally_ships (()) {" ".join(ships_left)})
(opponent_ships (()) {" ".join(opp_ships) if opp_ships else "none"})
"""

    def get_algorithm_move(
        self, player_idx: int, algorithm: str
    ) -> tuple[Optional[str], Optional[str]]:
        if algorithm != "random":
            return super().get_algorithm_move(player_idx, algorithm)

        if self.phase == "PLACEMENT":
            remaining = [
                s for s in self.ship_types if s[0] not in self.placed_ships[player_idx]
            ]
            ship_name, ship_len = random.choice(remaining)
            while True:
                col = random.randint(0, 9)
                row = random.randint(0, 9)
                orientation = random.choice(["h", "v"])
                # Check validity
                valid = True
                ship_coords = []
                for i in range(ship_len):
                    c, r = (col + i, row) if orientation == "h" else (col, row + i)
                    if (
                        not (0 <= c < 10 and 0 <= r < 10)
                        or (c, r) in self.boards[player_idx]
                    ):
                        valid = False
                        break
                    ship_coords.append((c, r))
                if valid:
                    return (
                        f"(place {ship_name} {self.format_coord(col, row)} {orientation})",
                        None,
                    )
        else:
            ships_remaining = len(self.ship_types) - len(self.sunk_ships[player_idx])
            targets = []
            valid_coords = [
                (c, r)
                for c in range(10)
                for r in range(10)
                if (c, r) not in self.shots_fired[player_idx]
            ]
            random.shuffle(valid_coords)
            for i in range(min(ships_remaining, len(valid_coords))):
                targets.append(self.format_coord(*valid_coords[i]))
            return f"(fire {' '.join(targets)})", None
