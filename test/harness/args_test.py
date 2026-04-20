import os
import subprocess
import sys
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


class TestServerArgs(unittest.TestCase):
    def test_shuffle_players_out_of_bounds_exits(self):
        cmd = [
            sys.executable,
            "src/sxpb_game/harness/sxpb_game_main.py",
            "--game",
            "tictactoe",
            "--players",
            "(()) (() (name A)) (() (name B))",
            "--shuffle_players",
            "0, 5",
        ]

        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=REPO_ROOT,
        )

        self.assertNotEqual(
            proc.returncode, 0, f"Expected non-zero exit code. Output:\n{proc.stdout}"
        )
        self.assertEqual(proc.returncode, 1)
        self.assertIn("Error: --shuffle_players index 5 out of bounds", proc.stdout)


if __name__ == "__main__":
    unittest.main()
