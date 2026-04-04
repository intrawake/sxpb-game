import os
import sys

# Ensure we can import from src
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))

from sxpb_game.by_title.mafia.logic import MafiaLogic


def test_discussion_count_with_dead_players():
    # 5 players: 1 Mafia, 1 Doctor, 1 Detective, 2 Villagers
    # Mafia kills p5 on Night 1.
    # On Day 1, there are 4 players alive.
    # They should speak 4 * 2 = 8 times total.

    game = MafiaLogic(num_players=5)

    # 1. Deal Roles
    game.make_move(0, "Mafia Doctor Detective Villager Villager")
    # p1=Mafia, p2=Doctor, p3=Detective, p4=Villager, p5=Villager

    # 2. Night Mafia Discussion
    game.make_move(1, "Let's kill p5")

    # 3. Night Mafia Vote
    game.make_move(1, "kill p5")

    # 4. Night Doctor
    game.make_move(2, "save p1")  # save someone else

    # 5. Night Detective
    game.make_move(3, "investigate p1")

    # Now it should be Day 1. p5 is dead.
    assert game.phase == "DAY_ORDER"
    game.make_move(0, "p1 p2 p3 p4")

    assert game.phase == "DAY_DISCUSSION"
    assert not game.alive[4]  # p5 is dead
    alive_count = sum(game.alive)
    assert alive_count == 4

    # Discussion turns
    turns = 0
    while game.phase == "DAY_DISCUSSION":
        curr = game.get_current_player()
        assert curr is not None
        game.make_move(curr, f"Talk {turns}")
        turns += 1
        if turns > 20:  # Safety break
            break

    assert game.phase == "DAY_ORDER"
    game.make_move(0, "p1 p2 p3 p4")

    while game.phase == "DAY_DISCUSSION":
        curr = game.get_current_player()
        assert curr is not None
        game.make_move(curr, f"Talk {turns}")
        turns += 1
        if turns > 20:  # Safety break
            break

    print(f"Total discussion turns: {turns}")
    assert turns == 8, f"Expected 8 turns (4 alive * 2), but got {turns}"


if __name__ == "__main__":
    try:
        test_discussion_count_with_dead_players()
        print("PASS: Discussion count is correct.")
    except Exception as e:
        print(f"FAIL: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
