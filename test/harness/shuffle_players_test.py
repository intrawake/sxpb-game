import sys
import os
import unittest

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src"))
)

from sxpb_game.harness import sxpb_game_main as server

shuffle_player_configs = getattr(server, "shuffle_player_configs")


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


if __name__ == "__main__":
    unittest.main()
