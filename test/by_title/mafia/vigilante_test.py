from sxpb_game.by_title.mafia.logic import MafiaLogic


def test_vigilante_shoots():
    game = MafiaLogic(num_players=7)

    assert game.phase == "DEAL_ROLES"
    assert game.make_move(0, "Mafia Mafia Villager Villager Doctor Vigilante").success

    assert game.phase == "NIGHT_MAFIA_DISCUSSION"
    assert game.make_move(1, "let's kill p3").success
    assert game.make_move(2, "yeah kill p3").success

    assert game.phase == "NIGHT_MAFIA_VOTE"
    assert game.make_move(1, "kill p3").success
    assert game.make_move(2, "kill p3").success

    assert game.phase == "NIGHT_DOCTOR"
    assert game.make_move(5, "save p4").success

    assert game.phase == "NIGHT_VIGILANTE"
    # p6 is the Vigilante
    assert game.get_current_player() == 6

    # Vigilante shoots p2 (a mafia)
    assert game.make_move(6, "shoot p2").success

    # Night resolves
    assert game.phase == "DAY_ORDER"
    game.make_move(0, "p1 p4 p5 p6")
    assert game.phase == "DAY_DISCUSSION"

    # p3 should be dead (killed by mafia)
    assert not game.alive[2]
    # p2 should be dead (killed by vigilante)
    assert not game.alive[1]

    # Run through day
    turns = 0
    while game.phase == "DAY_DISCUSSION":
        curr = game.get_current_player()
        assert curr is not None
        game.make_move(curr, "I am innocent!")
        turns += 1
        if turns > 20:
            break

    assert game.phase == "DAY_ORDER"

    # Send order based on surviving players (depends on the test: test 1 has p1, p4, p5, p6. test 2 has p1, p2, p4, p5, p6.)
    alive_str = " ".join([f"p{i + 1}" for i, a in enumerate(game.alive) if a])
    game.make_move(0, alive_str)

    while game.phase == "DAY_DISCUSSION":
        curr = game.get_current_player()
        assert curr is not None
        game.make_move(curr, "I am innocent!")
        turns += 1
        if turns > 20:
            break

    assert game.phase == "DAY_VOTE_ORDER"
    alive_str = " ".join([f"p{i + 1}" for i, a in enumerate(game.alive) if a])
    game.make_move(0, alive_str)
    assert game.phase == "DAY_VOTE"
    for i in range(6):
        if game.alive[i]:
            game.make_move(i + 1, "vote none")

    # Now it's night again
    assert game.phase == "NIGHT_MAFIA_DISCUSSION"
    assert game.make_move(
        1, "let's kill p4"
    ).success  # Wait p1 is still alive and is Mafia
    assert game.phase == "NIGHT_MAFIA_VOTE"
    assert game.make_move(1, "kill p4").success

    assert game.phase == "NIGHT_DOCTOR"
    assert game.make_move(5, "save p4").success

    assert game.phase == "NIGHT_VIGILANTE"
    # Vigilante has already shot, they shouldn't be asked to play
    assert game.get_current_player() == 0  # GM
    assert game.make_move(0, "skip").success  # GM skips

    assert game.phase == "DAY_ORDER"
    game.make_move(0, "p1 p5 p6")
    assert game.phase == "DAY_DISCUSSION"


def test_vigilante_skips():
    game = MafiaLogic(num_players=7)

    assert game.phase == "DEAL_ROLES"
    assert game.make_move(0, "Mafia Mafia Villager Villager Doctor Vigilante").success

    assert game.phase == "NIGHT_MAFIA_DISCUSSION"
    assert game.make_move(1, "let's kill p3").success
    assert game.make_move(2, "yeah kill p3").success

    assert game.phase == "NIGHT_MAFIA_VOTE"
    assert game.make_move(1, "kill p3").success
    assert game.make_move(2, "kill p3").success

    assert game.phase == "NIGHT_DOCTOR"
    assert game.make_move(5, "save p4").success

    assert game.phase == "NIGHT_VIGILANTE"
    # p6 is the Vigilante
    assert game.get_current_player() == 6

    # Vigilante skips
    assert game.make_move(6, "skip").success

    # Night resolves
    assert game.phase == "DAY_ORDER"
    game.make_move(0, "p1 p4 p5 p6")
    assert game.phase == "DAY_DISCUSSION"

    # Only p3 should be dead (killed by mafia)
    assert not game.alive[2]
    # Everyone else alive
    assert sum(game.alive) == 5

    # Run through day
    turns = 0
    while game.phase == "DAY_DISCUSSION":
        curr = game.get_current_player()
        assert curr is not None
        game.make_move(curr, "I am innocent!")
        turns += 1
        if turns > 20:
            break

    assert game.phase == "DAY_ORDER"

    # Send order based on surviving players (depends on the test: test 1 has p1, p4, p5, p6. test 2 has p1, p2, p4, p5, p6.)
    alive_str = " ".join([f"p{i + 1}" for i, a in enumerate(game.alive) if a])
    game.make_move(0, alive_str)

    while game.phase == "DAY_DISCUSSION":
        curr = game.get_current_player()
        assert curr is not None
        game.make_move(curr, "I am innocent!")
        turns += 1
        if turns > 20:
            break

    assert game.phase == "DAY_VOTE_ORDER"
    alive_str = " ".join([f"p{i + 1}" for i, a in enumerate(game.alive) if a])
    game.make_move(0, alive_str)
    assert game.phase == "DAY_VOTE"
    for i in range(6):
        if game.alive[i]:
            game.make_move(i + 1, "vote none")

    assert game.phase == "NIGHT_MAFIA_DISCUSSION"
    assert game.make_move(1, "let's kill p4").success
    assert game.make_move(2, "yeah").success
    assert game.phase == "NIGHT_MAFIA_VOTE"
    assert game.make_move(1, "kill p4").success
    assert game.make_move(2, "kill p4").success

    assert game.phase == "NIGHT_DOCTOR"
    assert game.make_move(5, "save p4").success

    assert game.phase == "NIGHT_VIGILANTE"
    # Vigilante skipped previously, they should still have their shot!
    assert game.get_current_player() == 6


def test_vigilante_shoots_after_detective():
    from sxpb_game.by_title.mafia.logic import MafiaLogic

    game = MafiaLogic(num_players=8)

    assert game.phase == "DEAL_ROLES"
    assert game.make_move(
        0, "Mafia Mafia Villager Villager Doctor Detective Vigilante"
    ).success

    assert game.phase == "NIGHT_MAFIA_DISCUSSION"
    assert game.make_move(1, "let's kill p3").success
    assert game.make_move(2, "yeah kill p3").success

    assert game.phase == "NIGHT_MAFIA_VOTE"
    assert game.make_move(1, "kill p3").success
    assert game.make_move(2, "kill p3").success

    assert game.phase == "NIGHT_DOCTOR"
    assert game.make_move(5, "save p4").success

    assert game.phase == "NIGHT_DETECTIVE"
    assert game.make_move(6, "investigate p1").success

    assert game.phase == "NIGHT_VIGILANTE", (
        f"Phase is {game.phase} instead of NIGHT_VIGILANTE"
    )
    # p7 is the Vigilante
    assert game.get_current_player() == 7

    # Vigilante shoots p2
    assert game.make_move(7, "shoot p2").success
