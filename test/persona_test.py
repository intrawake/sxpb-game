import os
import sys

# Ensure we can import from src
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

from sxpb_game.eval.utils import generate_prompt
from sxpb_game.eval.logic import GameLogic


class MockGame(GameLogic):
    def get_player_identifiers(self):
        return ["p1", "p2"]

    def render_player_view(self, player_idx):
        return "(board ...)"

    def get_prompt(self, player_idx):
        return "What's your move?"

    def get_valid_moves(self):
        return ["move1", "move2"]

    def get_rules(self):
        return "Don't lose."

    def get_visible_players(self, player_idx):
        return [0, 1]


def test_persona_injection():
    """Verify that secret persona is injected into the player's prompt, but not others."""
    game = MockGame()

    player_configs = [
        {
            "name": "Alice",
            "persona": "You are a mischievous goblin.",
        },
        {
            "name": "Bob",
            # No persona
        },
    ]

    # Generate prompt for player 0 (Alice)
    prompt_p1 = generate_prompt(game, 0, player_configs)

    assert "### Secret Persona" in prompt_p1, (
        "Persona section missing for player with persona."
    )
    assert "You are a mischievous goblin." in prompt_p1, "Persona text missing."
    assert "### Player Information" in prompt_p1, "Player info section missing."

    # Ensure rules appear before persona (just a rough check)
    assert prompt_p1.find("### Rules") < prompt_p1.find("### Secret Persona"), (
        "Rules should come before Secret Persona."
    )
    assert prompt_p1.find("### Secret Persona") < prompt_p1.find(
        "### Player Information"
    ), "Secret Persona should come before Player Information."

    # Generate prompt for player 1 (Bob)
    prompt_p2 = generate_prompt(game, 1, player_configs)

    assert "### Secret Persona" not in prompt_p2, (
        "Persona section should not appear for player without persona."
    )
    assert "You are a mischievous goblin." not in prompt_p2, (
        "Other player's persona leaked!"
    )

    print("PASS: Persona is correctly injected and scoped.")


if __name__ == "__main__":
    try:
        test_persona_injection()
    except Exception as e:
        print(f"FAIL: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
