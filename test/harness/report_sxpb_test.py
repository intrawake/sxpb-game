import sys
import os
import tempfile
import unittest
from unittest.mock import patch
from datetime import datetime, timezone

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src"))
)

from sxpb_game.by_title.tictactoe.logic import TicTacToeLogic
from sxpb_game.harness import sxpb_game_main as server

_write_report_sxpb = getattr(server, "_write_report_sxpb")

FROZEN_TIME = datetime(2026, 7, 10, 12, 0, 0, tzinfo=timezone.utc)

EXPECTED_WIN_LOSS = """\
(report
 (game tictactoe)
 (timestamp "2026-07-10T12:00:00Z")
 (players (())
  (()
   (name north)
   (model cohere/north-mini-code)
   (id X)
   (outcome win)
  )
  (()
   (name oss20b)
   (model openrouter/openai/gpt-oss-20b:free)
   (id O)
   (outcome loss)
  )
 )
)
; --- Move History ---
(moves (())
 Xa1 Oa2 Xb1 Ob2 Xc1
)

; --- Tic-Tac-Toe (3 Columns x 3 Rows) ---
(board
 ; Columns: a b c
 (row3 (()) _ _ _)
 (row2 (()) O O _)
 (row1 (()) X X X)
 ; Columns: a b c
)

; --- Game Metadata ---
(player_to_move O)
(move_count 5)
"""

EXPECTED_DRAW = """\
(report
 (game tictactoe)
 (timestamp "2026-07-10T12:00:00Z")
 (players (())
  (()
   (id X)
   (outcome draw)
  )
  (()
   (id O)
   (outcome draw)
  )
 )
)
; --- Move History ---
(moves (())
 Xa1 Ob2 Xa2 Ob1 Xb3 Oa3 Xc1 Oc3 Xc2
)

; --- Tic-Tac-Toe (3 Columns x 3 Rows) ---
(board
 ; Columns: a b c
 (row3 (()) O X O)
 (row2 (()) X O X)
 (row1 (()) X O X)
 ; Columns: a b c
)

; --- Game Metadata ---
(player_to_move O)
(move_count 9)
"""


class TestReportSxpb(unittest.TestCase):
    def _write(self, game_name, game, players, configs):
        with patch("sxpb_game.harness.sxpb_game_main.datetime") as mock_dt:
            mock_dt.now.return_value = FROZEN_TIME
            mock_dt.timezone = timezone
            mock_dt.strftime = datetime.strftime

            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".sxpb", delete=False
            ) as tmp:
                tmp_path = tmp.name

            try:
                _write_report_sxpb(tmp_path, game_name, game, players, configs)
                with open(tmp_path) as f:
                    return f.read()
            finally:
                os.unlink(tmp_path)

    def test_win_loss(self):
        game = TicTacToeLogic()
        for pid, move in [(0, "a1"), (1, "a2"), (0, "b1"), (1, "b2"), (0, "c1")]:
            game.make_move(pid, move)

        content = self._write(
            "tictactoe",
            game,
            game.get_player_identifiers(),
            [
                {"name": "north", "model": "cohere/north-mini-code"},
                {"name": "oss20b", "model": "openrouter/openai/gpt-oss-20b:free"},
            ],
        )
        self.assertEqual(content, EXPECTED_WIN_LOSS)

    def test_draw(self):
        game = TicTacToeLogic()
        moves = [
            (0, "a1"),
            (1, "b2"),
            (0, "a2"),
            (1, "b1"),
            (0, "b3"),
            (1, "a3"),
            (0, "c1"),
            (1, "c3"),
            (0, "c2"),
        ]
        for pid, move in moves:
            game.make_move(pid, move)

        content = self._write(
            "tictactoe",
            game,
            game.get_player_identifiers(),
            [{}, {}],
        )
        self.assertEqual(content, EXPECTED_DRAW)

    def test_na_for_missing_outcome(self):
        class PartialGame:
            def get_player_identifiers(self):
                return ["GM", "Player"]

            def get_player_outcomes(self):
                return {1: type("o", (), {"value": "win"})()}

            def render_player_full_sxpb(self, idx):
                return ";; na view"

        content = self._write(
            "blackjack",
            PartialGame(),
            ["GM", "Player"],
            [{}, {}],
        )

        self.assertIn("(outcome na)", content)
        self.assertIn("(outcome win)", content)
        self.assertIn(";; na view", content)


if __name__ == "__main__":
    unittest.main()
