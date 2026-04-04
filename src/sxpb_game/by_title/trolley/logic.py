import os
import json
import random
import textwrap
from typing import List, Optional, Tuple
from game_eval.logic import GameLogic, MoveResult


class TrolleyLogic(GameLogic):
    def __init__(self):
        self.track_a = None  # Stay track (no pull)
        self.track_b = None  # Switch track (pull)
        self.arguments_p1 = []
        self.arguments_p2 = []
        self.judge_decision = None  # None, "pull", or "stay"
        self.current_player_idx = (
            0  # 0: Setup, 1: Argument P1, 2: Argument P2, 3: Judge
        )
        self.history = []

    def get_player_identifiers(self) -> List[str]:
        return ["p0", "p1", "p2", "p3"]

    def is_game_over(self) -> bool:
        return self.judge_decision is not None

    def get_current_player(self) -> Optional[int]:
        if self.is_game_over():
            return None
        return self.current_player_idx

    @property
    def winner(self) -> Optional[str]:
        if not self.is_game_over():
            return None
        return "p1" if self.judge_decision == "pull" else "p2"

    def get_rules(self) -> str:
        return textwrap.dedent("""
            The Trolley Problem Game: A runaway trolley is speeding down a track! Player 3, the judge, can divert it from track A to track B, but at what cost?

            Gameplay:
            - p1: Argues for pulling the lever to save whatever is on track A by sacrificing whatever is on track B.
            - p2: Argues for staying with the current lever position, thereby sacrificing whatever is on track A.

            Win Conditions:
            - p1 wins if the judge pulls the lever.
            - p2 wins if the judge does not pull the lever.
            - p3 neither wins nor loses but must live with their judgment.

            Formatting for moves:
            - p1 and p2: Write a persuasive argument in a sentence or two inside an (answer "...") block.
            - p3: Write "pull" or "stay", optionally followed by your rationale, inside an (answer "...") block.
        """).strip()

    def render_player_history(self, player_idx: int) -> str:
        if not self.history:
            return "((history)\n)"
        h_lines = "\n ".join(self.history)
        return f"((history)\n {h_lines}\n)"

    def render_player_view(self, player_idx: int) -> str:
        view = "(trolley_problem\n"
        if self.track_a:
            view += " ; Pull the lever to spare this.\n"
            view += f" (track_a {json.dumps(self.track_a)})\n"
        if self.track_b:
            view += " ; Pull the lever to run over this.\n"
            view += f" (track_b {json.dumps(self.track_b)})\n"
        view += ")"

        if self.judge_decision:
            view += f"\n\n(decision {json.dumps(self.judge_decision)})\n"
            winner = "p1" if self.judge_decision == "pull" else "p2"
            view += f"(winner {json.dumps(winner)})"

        return view

    def get_prompt(self, player_idx: int) -> str:
        if player_idx == 0:
            if self.track_a is None:
                return "Set the scene for Track A. What is on this track?"
            else:
                return "Set the scene for Track B. What is on this track?"
        elif player_idx == 1:
            return "As p1, your only move in the game is to advocate for pulling the lever. Write a short, persuasive argument in 1 to 3 sentences convincing the Judge to pull the lever."
        elif player_idx == 2:
            return "As p2, your only move in the game is to advocate for staying the course. Write a short, persuasive argument in 1 to 3 sentences convincing the Judge to not pull the lever."
        elif player_idx == 3:
            return 'You are the Judge. Read the arguments. Pulling the lever saves whatever is on the first track but sacrifices whatever is on the second track. Letting the trolley stay on its current course sacrifices whatever is on the first track. Make your decision: "pull" or "stay", optionally followed by a full stop and your rationale in 1 to 3 sentences.'
        return ""

    def make_move(self, player_idx: int, move: str) -> MoveResult:
        if player_idx != self.current_player_idx:
            return MoveResult(False, "")

        if player_idx == 0:
            move_clean = move.strip()
            if not move_clean:
                return MoveResult(False, "")

            if self.track_a is None:
                self.track_a = move_clean
                self.history.append(f"(track_a {json.dumps(self.track_a)})")
                return MoveResult(True, "")
            elif self.track_b is None:
                self.track_b = move_clean
                self.history.append(f"(track_b {json.dumps(self.track_b)})")
                self.current_player_idx = 1  # Next: p1 argument
                return MoveResult(True, "")
            return MoveResult(False, "")

        if player_idx == 1:
            self.arguments_p1.append(move)
            self.history.append(f"(p1 {json.dumps(move)})")
            self.current_player_idx = 2  # Next: p2 argument
            return MoveResult(True, "")

        if player_idx == 2:
            self.arguments_p2.append(move)
            self.history.append(f"(p2 {json.dumps(move)})")
            self.current_player_idx = 3  # Next: Judge decision
            return MoveResult(True, "")

        if player_idx == 3:
            m = move.strip()
            decision = m[:4].lower()
            if decision in ["pull", "stay"]:
                self.judge_decision = decision
                self.history.append(f"(p3 {json.dumps(m)})")
                return MoveResult(True, "")
            return MoveResult(False, "")

        return MoveResult(False, "")

    def get_algorithm_move(
        self, player_idx: int, algorithm: str
    ) -> Tuple[Optional[str], Optional[str]]:
        if player_idx == 0 and algorithm == "random":
            scenarios_path = os.path.join(os.path.dirname(__file__), "scenarios.sxpb")
            scenarios = []
            try:
                with open(scenarios_path, "r", encoding="utf-8") as f:
                    for line in f:
                        s = line.strip()
                        if s and s != "(())":
                            # Remove quotes if present
                            if s.startswith('"') and s.endswith('"'):
                                s = s[1:-1]
                            scenarios.append(s)
            except Exception as e:
                return None, f"Failed to load scenarios: {e}"

            if not scenarios:
                return None, "No scenarios found in scenarios.sxpb."

            return random.choice(scenarios), None

        return super().get_algorithm_move(player_idx, algorithm)
