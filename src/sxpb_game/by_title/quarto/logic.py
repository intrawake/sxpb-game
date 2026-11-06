import random
from typing import Optional

import sxpb

from sxpb_game.eval.logic import GameLogic, MoveResult, read_rulebook


LETTERS = "potudahiPOTUDAHI"
# Attribute values for index bits, least significant first.
ATTRIBUTE_VALUES = (
    ("consonant", "vowel"),
    ("hole", "no-hole"),
    ("last-half", "first-half"),
    ("lower", "upper"),
)
SQUARES = tuple(f"{col}{row}" for row in range(1, 5) for col in "abcd")
LINES = (
    tuple((f"row{row}", tuple(f"{col}{row}" for col in "abcd")) for row in range(1, 5))
    + tuple(
        (f"col{col}", tuple(f"{col}{row}" for row in range(1, 5))) for col in "abcd"
    )
    + (
        ("diagonal_a1_d4", ("a1", "b2", "c3", "d4")),
        ("diagonal_a4_d1", ("a4", "b3", "c2", "d1")),
    )
)


def _parse_piece(token: str) -> Optional[int]:
    return LETTERS.index(token) if len(token) == 1 and token in LETTERS else None


def _piece_symbol(piece: Optional[int]) -> str:
    return LETTERS[piece] if piece is not None else "_"


class QuartoLogic(GameLogic):
    def __init__(self, num_players: int = 2):
        if num_players != 2:
            raise ValueError("Quarto requires exactly two players.")
        self.board: dict[str, Optional[int]] = dict.fromkeys(SQUARES)
        self.available_pieces = list(range(len(LETTERS)))
        self.offered_piece: Optional[int] = None
        self.current_player = 0
        self.move_count = 0
        self.history = sxpb.Many()
        self.winner: Optional[str] = None
        self.winning_line: Optional[str] = None
        self.winning_attributes: list[str] = []

    def get_player_identifiers(self) -> list[str]:
        return ["p1", "p2"]

    def is_game_over(self) -> bool:
        return self.winner is not None

    def get_current_player(self) -> Optional[int]:
        return None if self.is_game_over() else self.current_player

    def get_rules(self) -> str:
        return read_rulebook(__file__)

    def get_prompt(self, player_idx: int) -> str:
        if self.is_game_over():
            return "The game is over."
        if self.offered_piece is None:
            return "Choose your opponent's first piece: give <piece>."
        return (
            f"Place {LETTERS[self.offered_piece]} and choose your opponent's next piece: "
            "place <square> give <piece>. On a winning or final placement, "
            "place <square> is sufficient."
        )

    def _winning_alignment(
        self, square: str, piece: int
    ) -> tuple[Optional[str], list[str]]:
        """Check a hypothetical placement without changing the board."""
        for name, line in LINES:
            if square not in line:
                continue
            pieces = [piece if pos == square else self.board[pos] for pos in line]
            if any(value is None for value in pieces):
                continue
            attributes = [
                values[(piece >> index) & 1]
                for index, values in enumerate(ATTRIBUTE_VALUES)
                if all(
                    value is not None and (value ^ piece) & (1 << index) == 0
                    for value in pieces
                )
            ]
            if attributes:
                return name, attributes
        return None, []

    def make_move(self, player_idx: int, move: str) -> MoveResult:
        if self.is_game_over():
            return MoveResult(False, "The game is over.")
        if player_idx != self.current_player:
            return MoveResult(False, "It is not your turn.")
        tokens = move.split()
        if self.offered_piece is None:
            if len(tokens) != 2 or tokens[0].lower() != "give":
                return MoveResult(False, "Choose the first piece with give <piece>.")
            gift = _parse_piece(tokens[1])
            if gift is None or gift not in self.available_pieces:
                return MoveResult(False, "Choose a piece from available_pieces.")
            self.available_pieces.remove(gift)
            self.offered_piece = gift
            command = f"give {LETTERS[gift]}"
        else:
            if (
                len(tokens) not in (2, 4)
                or tokens[0].lower() != "place"
                or (len(tokens) == 4 and tokens[2].lower() != "give")
            ):
                return MoveResult(False, "Use place <square> give <piece>.")
            square = tokens[1].lower()
            if square not in self.board or self.board[square] is not None:
                return MoveResult(False, "Choose an empty square from a1 through d4.")
            gift = _parse_piece(tokens[3]) if len(tokens) == 4 else None
            if len(tokens) == 4 and (gift is None or gift not in self.available_pieces):
                return MoveResult(False, "The gift must be in available_pieces.")
            line, attributes = self._winning_alignment(square, self.offered_piece)
            final_placement = all(
                pos == square or piece is not None for pos, piece in self.board.items()
            )
            if line is None and not final_placement and gift is None:
                return MoveResult(
                    False, "Also choose your opponent's next piece: give <piece>."
                )

            # Commit only after validating the entire compound move.
            self.board[square] = self.offered_piece
            self.offered_piece = None
            if line is not None:
                self.winner = self.get_player_identifiers()[player_idx]
                self.winning_line = line
                self.winning_attributes = attributes
            elif final_placement:
                self.winner = "Draw"
            else:
                assert gift is not None
                self.available_pieces.remove(gift)
                self.offered_piece = gift
            command = f"place {square}" + (
                f" give {LETTERS[gift]}" if gift is not None else ""
            )

        self.history.append(
            sxpb.Lone({self.get_player_identifiers()[player_idx]: command})
        )
        self.move_count += 1
        self.current_player = 1 - self.current_player
        return MoveResult(True, "")

    def render_player_history(self, player_idx: int) -> str:
        return (
            "; --- Move History ---\n" + sxpb.dumps({"history": self.history}).strip()
        )

    def render_player_view(self, player_idx: int) -> str:
        player = self.get_current_player()
        # Only fixed letter IDs and empty markers enter this compact grid.
        rows = [
            f" (row{row} (()) "
            + " ".join(_piece_symbol(self.board[f"{col}{row}"]) for col in "abcd")
            + ")"
            for row in range(4, 0, -1)
        ]
        board = "(board\n ; Columns: a b c d\n" + "\n".join(rows) + "\n)"
        metadata = {
            "available_pieces": [LETTERS[piece] for piece in self.available_pieces],
            "offered_piece": _piece_symbol(self.offered_piece),
            "player_to_move": self.get_player_identifiers()[player]
            if player is not None
            else "_",
            "move_count": self.move_count,
        }
        if self.winner is not None:
            metadata["winner"] = self.winner
        return board + "\n" + sxpb.dumps(metadata).strip()

    def get_algorithm_move(
        self, player_idx: int, algorithm: str
    ) -> tuple[Optional[str], Optional[str]]:
        if algorithm != "random":
            return super().get_algorithm_move(player_idx, algorithm)
        if self.get_current_player() != player_idx:
            return None, "It is not your turn or the game is over."
        if self.offered_piece is None:
            return f"give {LETTERS[random.choice(self.available_pieces)]}", None
        square = random.choice(
            [pos for pos, piece in self.board.items() if piece is None]
        )
        gift = (
            f" give {LETTERS[random.choice(self.available_pieces)]}"
            if self.available_pieces
            else ""
        )
        return f"place {square}{gift}", None
