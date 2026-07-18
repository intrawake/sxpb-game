from __future__ import annotations

from enum import Enum
from typing import List, NamedTuple, Optional, Tuple


class Outcome(Enum):
    WIN = "win"
    DRAW = "draw"
    LOSS = "loss"


OUTCOME_TO_SCORE = {Outcome.WIN: 1.0, Outcome.DRAW: 0.5, Outcome.LOSS: 0.0}


class MoveResult(NamedTuple):
    success: bool
    reason: str


class GameLogic:
    def get_player_identifiers(self) -> List[str]:
        """Returns a list of valid player identifiers for the game."""
        raise NotImplementedError

    def get_outcome_player_indices(self) -> List[int]:
        """Return indices of players that receive win/draw/loss outcomes."""
        return list(range(len(self.get_player_identifiers())))

    def get_visible_players(self, player_idx: int) -> List[int]:
        """Returns a list of player indices that are visible to the given player.

        NOTE: This defaults to an empty list to ensure anonymity between players
        (e.g., in Tic-Tac-Toe, agents shouldn"t see each other's metadata like
        model names or pronouns). Games with visible identities (like Mafia)
        must explicitly override this.
        """
        return []

    def render_player_view(self, player_idx: int) -> str:
        """Returns the SxPB-formatted string representation of the game state from the player's perspective."""
        raise NotImplementedError

    def render_player_history(self, player_idx: int) -> str:
        """Returns the SxPB-formatted string representing the history of moves, or empty string if not applicable."""
        return ""

    def render_player_full_sxpb(self, player_idx: int) -> str:
        """Returns the complete SxPB-formatted string combining history and state, with history first."""
        view = self.render_player_view(player_idx).strip()
        history = self.render_player_history(player_idx).strip()
        if history:
            return f"{history}\n\n{view}"
        return view

    def is_game_over(self) -> bool:
        """Returns whether the game is over."""
        raise NotImplementedError

    def get_current_player(self) -> Optional[int]:
        """Returns the index of the player whose turn it is, or None if the game is over."""
        raise NotImplementedError

    def get_prompt(self, player_idx: int) -> str:
        """Returns a short string prompting the player to make a move."""
        raise NotImplementedError

    def make_move(self, player_idx: int, move: str) -> MoveResult:
        """Applies the given move for the given player index. Returns a MoveResult."""
        raise NotImplementedError

    def get_algorithm_move(
        self, player_idx: int, algorithm: str
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Executes the specified algorithm to return a string representing the next move.
        Returns a tuple of (move_string, error_message).
        """
        return None, f"Algorithm '{algorithm}' not supported for this game."

    def get_player_outcomes(self) -> dict[int, Outcome]:
        """Return player-index → Outcome.

        The default handles simple 2-player / N-player games where
        ``self.winner`` is a player identifier (from
        ``get_player_identifiers()``) or ``"Draw"``.  Team-based and
        hidden-role games override this.
        """
        winner = getattr(self, "winner", None)
        pids = self.get_player_identifiers()
        outcome_player_indices = self.get_outcome_player_indices()
        if winner == "Draw":
            return {i: Outcome.DRAW for i in outcome_player_indices}
        if isinstance(winner, str) and winner in pids:
            winner_index = pids.index(winner)
            if winner_index not in outcome_player_indices:
                return {}
            return {
                i: (Outcome.WIN if i == winner_index else Outcome.LOSS)
                for i in outcome_player_indices
            }
        return {}

    def get_rules(self) -> str:
        """Returns the rules of the game to be prepended to the player's prompt."""
        return ""


def read_rulebook(logic_file_path: str) -> str:
    """Reads the rulebook.md file residing in the same directory as the given logic file."""
    import os

    rulebook_path = os.path.join(os.path.dirname(logic_file_path), "rulebook.md")
    try:
        with open(rulebook_path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        return ""
