import os
import sys

# Ensure we can import from src
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

import sxpb
from sxpb_game.eval.utils import get_player_by_identifier_sxpb


def test_player_metadata_filtering():
    """Verify that only shared fields are visible in player info."""
    players = ["p1", "p2", "p3"]
    player_configs = [
        {
            "name": "Alice",
            "pronoun": "she",
            "model": "gpt-4",
            "secret": "shh",
            "bio": "A smart cat.",
        },
        {"name": "Bob", "pronoun": "he", "algorithm": "random", "extra": "data"},
        {"name": "Charlie", "pronoun": "they"},
    ]
    # Simulate visible players
    visible_indices = [0, 1]

    result_sxpb = get_player_by_identifier_sxpb(
        players, player_configs, visible_indices
    )

    result = sxpb.loads(result_sxpb)
    assert isinstance(result, dict), f"Expected dict, got {type(result)}"

    info = result.get("player_by_identifier")
    assert isinstance(info, dict), (
        f"Expected dict for player_by_identifier, got {type(info)}"
    )

    # Check p1's info
    p1_info = info.get("p1")
    assert isinstance(p1_info, dict)
    assert "name" in p1_info
    assert p1_info["name"] == "Alice"
    assert "pronoun" in p1_info
    assert "bio" in p1_info
    assert p1_info["bio"] == "A smart cat."
    assert "model" not in p1_info, "Model should be hidden!"
    assert "secret" not in p1_info, "Secret fields should be hidden!"

    # Check p2's info
    p2_info = info.get("p2")
    assert isinstance(p2_info, dict)
    assert "name" in p2_info
    assert p2_info["name"] == "Bob"
    assert "pronoun" in p2_info
    assert "algorithm" not in p2_info, "Algorithm should be hidden!"
    assert "extra" not in p2_info, "Extra fields should be hidden!"

    # Check p3 is not in info
    assert "p3" not in info

    print("PASS: Player metadata is correctly filtered.")


if __name__ == "__main__":
    try:
        test_player_metadata_filtering()
    except Exception as e:
        print(f"FAIL: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
