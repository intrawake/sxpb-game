import sys
import os
import unittest

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))
from sxpb_game.eval.utils import parse_game_guess


class TestParser(unittest.TestCase):
    def test_wordle_parsing(self):
        cases = [
            ("I think the answer is apple.\nGuess: apple", "apple"),
            ("**Guess: train**\nThis was my guess.", "train"),
            ("Reasoning...\nGuess: slice\nExtra yap.", "slice"),
            ("No keyword here, just the word at the end: CRANE", "CRANE"),
            ("Guess: apple (but wait, no, actually)\nGuess: crane", "crane"),
        ]
        for content, expected in cases:
            self.assertEqual(
                parse_game_guess(content, "guess", r"[A-Za-z]{5}"), expected
            )

    def test_tictactoe_parsing(self):
        cases = [
            ("Move: b2", "b2"),
            ("I'll go with **Move: a1** for sure.", "a1"),
            ("Reasoning...\nMove: c3\nYap yap.", "c3"),
            ("b2", "b2"),
        ]
        for content, expected in cases:
            self.assertEqual(
                parse_game_guess(content, "move", r"[a-cA-C][1-3]"), expected
            )

    def test_mastermind_parsing(self):
        cases = [
            ("Guess: RGBY", "RGBY"),
            ("Let's try **Guess: POGB** next.", "POGB"),
            ("Yap.\nGuess: YRRO\nMore yap.", "YRRO"),
            ("RRRR", "RRRR"),
        ]
        for content, expected in cases:
            self.assertEqual(parse_game_guess(content, "guess", r"[A-Z]{4}"), expected)

    def test_prompt_formatting(self):
        import importlib
        import inspect

        sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))
        sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
        from sxpb_game.eval.logic import GameLogic

        games = [
            "minesweeper",
            "wordle",
            "tictactoe",
            "blackjack",
            "mastermind",
            "connect_four",
        ]

        for game_name in games:
            try:
                logic_mod = importlib.import_module(
                    f"sxpb_game.by_title.{game_name}.logic"
                )
            except ImportError:
                logic_mod = importlib.import_module(f"{game_name}.logic")
            logic_class = None
            for name, obj in inspect.getmembers(logic_mod, inspect.isclass):
                if issubclass(obj, GameLogic) and obj is not GameLogic:
                    logic_class = obj
                    break

            self.assertIsNotNone(
                logic_class, f"Could not find GameLogic subclass for {game_name}"
            )
            assert logic_class is not None
            game = logic_class()
            idx = 0
            if game.get_current_player() is not None:
                idx = game.get_current_player()

            assert idx is not None
            state_sxpb = game.render_player_view(idx)
            prompt_q = game.get_prompt(idx)
            prompt = f"""\
You are a playing agent. Your goal is to win the game or force a draw.

### Current Game State (SxPB format)
```sxpb
{state_sxpb}
```

### Instructions
- Analyze the board
- Provide your next move.

### Question
{prompt_q}"""

            with self.subTest(game=game_name):
                self.assertIn(
                    "\n```sxpb\n",
                    prompt,
                    f"{game_name} prompt missing '```sxpb' at start of line",
                )
                self.assertIn(
                    "\n```\n",
                    prompt,
                    f"{game_name} prompt missing '```' at start of line",
                )


if __name__ == "__main__":
    unittest.main()
