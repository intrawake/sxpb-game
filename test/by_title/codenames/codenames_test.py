import sys
import os
import unittest

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from sxpb_game.by_title.codenames.logic import CodenamesLogic


class TestCodenames(unittest.TestCase):
    def test_initial_state(self):
        logic = CodenamesLogic()
        self.assertEqual(len(logic.words), 25)
        self.assertEqual(len(logic.word_colors), 25)

        red_count = sum(1 for v in logic.word_colors.values() if v == "red")
        blue_count = sum(1 for v in logic.word_colors.values() if v == "blue")
        assassin_count = sum(1 for v in logic.word_colors.values() if v == "assassin")
        neutral_count = sum(1 for v in logic.word_colors.values() if v == "neutral")

        self.assertEqual(red_count, 9)
        self.assertEqual(blue_count, 8)
        self.assertEqual(assassin_count, 1)
        self.assertEqual(neutral_count, 7)

        self.assertEqual(logic.get_current_player(), 1)  # Red Spymaster
        self.assertFalse(logic.is_game_over())

    def test_game_flow(self):
        logic = CodenamesLogic()

        # Override words for deterministic testing
        logic.words = [f"WORD{i}" for i in range(25)]
        logic.word_colors = {
            "WORD0": "red",
            "WORD1": "red",
            "WORD2": "blue",
            "WORD3": "neutral",
            "WORD4": "assassin",
        }
        for i in range(5, 25):
            logic.word_colors[f"WORD{i}"] = (
                "red" if i < 12 else ("blue" if i < 19 else "neutral")
            )

        # 1: Red Spymaster, 2: Blue Spymaster, 3: Red Operative, 4: Blue Operative
        self.assertEqual(logic.get_current_player(), 1)

        # Red Spymaster gives a clue
        self.assertTrue(logic.make_move(1, "HINT 2").success)
        self.assertEqual(logic.get_current_player(), 3)
        self.assertEqual(logic.guesses_left, 3)

        # Red Operative guesses correctly
        self.assertTrue(logic.make_move(3, "WORD0").success)
        self.assertIn("WORD0", logic.revealed)
        self.assertEqual(logic.get_current_player(), 3)
        self.assertEqual(logic.guesses_left, 2)

        # Red Operative guesses neutral
        self.assertTrue(logic.make_move(3, "WORD3").success)
        self.assertIn("WORD3", logic.revealed)
        self.assertEqual(logic.get_current_player(), 2)  # Switch to Blue Spymaster

        # Blue Spymaster gives a clue
        self.assertTrue(logic.make_move(2, "BLUEHINT 1").success)
        self.assertEqual(logic.get_current_player(), 4)

        # Blue Operative stops early
        self.assertTrue(logic.make_move(4, ".").success)
        self.assertEqual(logic.get_current_player(), 1)  # Switch back to Red Spymaster

        # Red Spymaster turn again
        self.assertTrue(logic.make_move(1, "DANGER 1").success)
        self.assertEqual(logic.get_current_player(), 3)

        # Red Operative guesses Assassin
        self.assertTrue(logic.make_move(3, "WORD4").success)
        self.assertTrue(logic.is_game_over())
        self.assertEqual(logic.winner, "blue")

        history_output = logic.render_player_history(0)
        self.assertIn("(history)", history_output)
        self.assertIn('(p1 "HINT 2")', history_output)
        self.assertIn("(p3 WORD0)", history_output)
        self.assertIn("(reveal red)", history_output)
        self.assertIn("(p3 WORD3)", history_output)
        self.assertIn("(reveal neutral)", history_output)
        self.assertIn('(p2 "BLUEHINT 1")', history_output)
        self.assertIn('(p4 ".")', history_output)
        self.assertIn('(p1 "DANGER 1")', history_output)
        self.assertIn("(p3 WORD4)", history_output)
        self.assertIn("(reveal assassin)", history_output)

    def test_invalid_moves(self):
        logic = CodenamesLogic()

        # Override words for deterministic testing
        logic.words = [f"WORD{i}" for i in range(25)]
        logic.word_colors = {f"WORD{i}": "red" for i in range(25)}

        self.assertEqual(logic.get_current_player(), 1)

        # Spymaster giving a word that is on the table
        self.assertFalse(logic.make_move(1, "WORD0 2").success)

        # Spymaster giving a valid clue
        self.assertTrue(logic.make_move(1, "HINT 2").success)
        self.assertEqual(logic.get_current_player(), 3)

        # Operative guessing a word not on the table
        self.assertFalse(logic.make_move(3, "NOTONBOARD").success)

        # Operative guessing a word that is on the table
        self.assertTrue(logic.make_move(3, "WORD0").success)

        # Operative guessing a word already revealed
        self.assertFalse(logic.make_move(3, "WORD0").success)


if __name__ == "__main__":
    unittest.main()
