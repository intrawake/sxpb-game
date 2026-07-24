import sys
import os
import tempfile
import unittest

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src"))
)

import sxpb
from sxpb_game.harness import sxpb_game_main as server

shuffle_player_configs = getattr(server, "shuffle_player_configs")
shuffle_outcome_player_configs = getattr(server, "shuffle_outcome_player_configs")
_write_report_sxpb = getattr(server, "_write_report_sxpb")


def fake_randint(low, high):
    return low


class TestShufflePlayers(unittest.TestCase):
    def test_shuffle_player_configs_basic(self):
        configs = ["A", "B", "C", "D"]
        indices_str = "0, 2"
        # 0 and 2 are A and C.
        # i=0: swap 0,0
        # i=2: swap 2,0
        # Result: C, B, A, D
        shuffle_player_configs(configs, indices_str, randint_func=fake_randint)
        self.assertEqual(configs, ["C", "B", "A", "D"])

    def test_shuffle_player_configs_out_of_bounds_exits(self):
        configs = ["A", "B", "C"]
        indices_str = "1, 5, 2"
        with self.assertRaises(SystemExit) as cm:
            shuffle_player_configs(configs, indices_str, randint_func=fake_randint)
        self.assertEqual(cm.exception.code, 1)

    def test_shuffle_player_configs_duplicates_ignored(self):
        configs = ["A", "B", "C"]
        indices_str = "0, 1, 1"
        # Valid: 0, 1 (A, B)
        # i=0: swap 0,0
        # i=1: swap 1,0
        # Result: B, A, C
        shuffle_player_configs(configs, indices_str, randint_func=fake_randint)
        self.assertEqual(configs, ["B", "A", "C"])

    def test_shuffle_player_configs_messy_string(self):
        configs = ["A", "B", "C", "D"]
        indices_str = "shuffle player [1] and [3] please!"
        # Valid: 1, 3 (B, D)
        # i=1: swap 1,1
        # i=3: swap 3,1
        # Result: A, D, C, B
        shuffle_player_configs(configs, indices_str, randint_func=fake_randint)
        self.assertEqual(configs, ["A", "D", "C", "B"])

    def test_shuffle_player_configs_rotation(self):
        configs = ["A", "B", "C", "D", "E"]
        indices_str = "0, 1, 2"
        # Valid: 0, 1, 2 (A, B, C)
        # i=0: swap 0,0 -> A, B, C, D, E
        # i=1: swap 1,0 -> B, A, C, D, E
        # i=2: swap 2,0 -> C, A, B, D, E
        # Result: C, A, B, D, E
        shuffle_player_configs(configs, indices_str, randint_func=fake_randint)
        self.assertEqual(configs, ["C", "A", "B", "D", "E"])


class FakeGame:
    """Minimal game stub with configurable outcome-bearing indices."""

    def __init__(self, outcome_indices):
        self._outcome_indices = outcome_indices

    def get_outcome_player_indices(self):
        return list(self._outcome_indices)


class TestShuffleOutcomePlayers(unittest.TestCase):
    def test_shuffles_only_outcome_indices(self):
        """Non-outcome configs (e.g. GM at index 0) stay put."""
        configs = ["GM", "A", "B", "C"]
        game = FakeGame([1, 2, 3])
        # fake_randint always picks low → deterministic rotation.
        result = shuffle_outcome_player_configs(
            game, configs, randint_func=fake_randint
        )
        self.assertEqual(result, [1, 2, 3])
        # fake_randint always returns low → deterministic rotation:
        # n=0: swap(1,1) → GM A B C
        # n=1: swap(2,1) → GM B A C
        # n=2: swap(3,1) → GM C A B
        self.assertEqual(configs, ["GM", "C", "A", "B"])

    def test_all_players_outcome(self):
        """When every player is outcome-bearing, behaves like full shuffle."""
        configs = ["A", "B", "C"]
        game = FakeGame([0, 1, 2])
        shuffle_outcome_player_configs(game, configs, randint_func=fake_randint)
        # Same rotation as explicit "0, 1, 2":
        # n=0: swap(0,0) → A B C
        # n=1: swap(1,0) → B A C
        # n=2: swap(2,0) → C A B
        self.assertEqual(configs, ["C", "A", "B"])

    def test_single_outcome_player_noop(self):
        """A single outcome-bearing player cannot be shuffled."""
        configs = ["GM", "A"]
        game = FakeGame([1])
        result = shuffle_outcome_player_configs(
            game, configs, randint_func=fake_randint
        )
        self.assertEqual(result, [1])
        self.assertEqual(configs, ["GM", "A"])

    def test_returns_outcome_indices(self):
        configs = ["GM", "A", "B"]
        game = FakeGame([1, 2])
        result = shuffle_outcome_player_configs(
            game, configs, randint_func=fake_randint
        )
        self.assertEqual(result, [1, 2])


class TestShuffledReportConsistency(unittest.TestCase):
    """The report must reflect the *shuffled* seat assignment, not the original."""

    @staticmethod
    def _parse_report_players(report_path):
        """Parse the (report ...) header block and return its players list."""
        with open(report_path) as f:
            content = f.read()
        # The header is the first SxPB expression; the game view follows.
        # Collect lines until parentheses balance.
        depth = 0
        header_lines = []
        for line in content.splitlines():
            header_lines.append(line)
            depth += line.count("(") - line.count(")")
            if depth <= 0 and header_lines:
                break
        parsed = sxpb.loads("\n".join(header_lines))
        assert isinstance(parsed, dict)
        report = parsed["report"]
        assert isinstance(report, dict)
        return report["players"]

    def _play_tictactoe_x_wins(self):
        from sxpb_game.by_title.tictactoe.logic import TicTacToeLogic

        game = TicTacToeLogic()
        # X: a1, a2, a3 (column a sweep).  O: b1, b2.
        for idx, move in [(0, "a1"), (1, "b1"), (0, "a2"), (1, "b2"), (0, "a3")]:
            valid, _ = game.make_move(idx, move)
            assert valid, f"move {move} rejected"
        assert game.is_game_over()
        return game

    def test_report_reflects_shuffled_players(self):
        game = self._play_tictactoe_x_wins()
        players = game.get_player_identifiers()  # ["X", "O"]

        # Original order: model-alpha at seat 0, model-beta at seat 1.
        player_configs = [
            {"model": "model-alpha"},
            {"model": "model-beta"},
        ]

        # Deterministic shuffle swaps seats 0 and 1:
        #   n=0: swap(0,0) → alpha beta
        #   n=1: swap(1,0) → beta alpha
        shuffle_outcome_player_configs(game, player_configs, randint_func=fake_randint)
        self.assertEqual(player_configs[0]["model"], "model-beta")
        self.assertEqual(player_configs[1]["model"], "model-alpha")

        # Build ELO keys the same way the harness does (post-shuffle).
        elo_key_by_player_index = {
            0: player_configs[0]["model"],
            1: player_configs[1]["model"],
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".sxpb", delete=False) as f:
            report_path = f.name

        try:
            _write_report_sxpb(
                report_path,
                "tictactoe",
                game,
                players,
                player_configs,
                elo_key_by_player_index=elo_key_by_player_index,
            )

            report_players = self._parse_report_players(report_path)

            # Seat 0 (X, winner) must carry the *shuffled* model.
            self.assertEqual(report_players[0]["model"], "model-beta")
            self.assertEqual(report_players[0]["rating_alias"], "model-beta")
            self.assertEqual(report_players[0]["outcome"], "win")

            # Seat 1 (O, loser) likewise.
            self.assertEqual(report_players[1]["model"], "model-alpha")
            self.assertEqual(report_players[1]["rating_alias"], "model-alpha")
            self.assertEqual(report_players[1]["outcome"], "loss")
        finally:
            os.unlink(report_path)

    def test_report_without_shuffle_keeps_original_order(self):
        """Control: no shuffle → report matches the original config order."""
        game = self._play_tictactoe_x_wins()
        players = game.get_player_identifiers()

        player_configs = [
            {"model": "model-alpha"},
            {"model": "model-beta"},
        ]
        elo_key_by_player_index = {0: "model-alpha", 1: "model-beta"}

        with tempfile.NamedTemporaryFile(mode="w", suffix=".sxpb", delete=False) as f:
            report_path = f.name

        try:
            _write_report_sxpb(
                report_path,
                "tictactoe",
                game,
                players,
                player_configs,
                elo_key_by_player_index=elo_key_by_player_index,
            )

            report_players = self._parse_report_players(report_path)

            self.assertEqual(report_players[0]["model"], "model-alpha")
            self.assertEqual(report_players[0]["rating_alias"], "model-alpha")
            self.assertEqual(report_players[1]["model"], "model-beta")
            self.assertEqual(report_players[1]["rating_alias"], "model-beta")
        finally:
            os.unlink(report_path)


if __name__ == "__main__":
    unittest.main()
