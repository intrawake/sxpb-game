from sxpb_game.by_title.resistance.logic import ResistanceLogic


def test_resistance_basic_flow():
    game = ResistanceLogic(num_players=5)
    assert game.phase == "DEAL_ROLES"
    assert game.get_current_player() == 0

    # GM deals roles
    res = game.make_move(0, "Spy Spy Resistance Resistance Resistance")
    assert res.success

    assert game.phase == "PROPOSE_SQUAD"
    assert game.get_current_player() == 1  # p1 is leader

    # p1 proposes squad
    res = game.make_move(1, "propose p1 p2")
    assert res.success
    assert game.phase == "VOTE_ON_SQUAD"

    # Everyone else votes (leader p1 already voted approve)
    for i in range(2, 6):
        assert game.make_move(i, "vote approve").success

    assert game.phase == "MISSION_VOTE"
    assert game.vote_track == 0

    # p1 and p2 are on squad
    # p1 is Spy, p2 is Spy
    # (Since they are spies, they are NOT automated)
    assert game.make_move(1, "play sabotage").success
    assert game.make_move(2, "play sabotage").success

    assert game.phase == "DISCUSSION_ORDER"
    assert game.round == 2
    assert game.leader_idx == 1  # p2 is leader
    assert game.score_spies == 1
    assert game.score_resistance == 0
    assert len(game.completed_missions) == 1
    assert game.completed_missions[0]["sabotage_count"] == 2

    # GM sets discussion order
    assert game.make_move(0, "p1 p2 p3 p4 p5").success
    assert game.phase == "DISCUSSION"

    # Discussion
    for i in range(1, 6):
        assert game.make_move(i, "I am innocent").success

    assert game.phase == "PROPOSE_SQUAD"


def test_five_failed_votes():
    game = ResistanceLogic(5)
    game.make_move(0, "Spy Spy Resistance Resistance Resistance")

    for _ in range(4):
        assert game.phase == "PROPOSE_SQUAD"
        leader = game.get_current_player()
        assert leader is not None
        assert game.make_move(leader, "propose p1 p2").success
        for i in range(1, 6):
            if i == leader:
                continue
            game.make_move(i, "vote reject")

        assert game.phase == "DISCUSSION_ORDER"
        assert not game.is_game_over()

        game.make_move(0, "p1 p2 p3 p4 p5")
        for i in range(1, 6):
            game.make_move(i, "Bad squad")

        assert game.phase == "PROPOSE_SQUAD"

    leader = game.get_current_player()
    assert leader is not None
    game.make_move(leader, "propose p1 p2")
    for i in range(1, 6):
        if i == leader:
            continue
        game.make_move(i, "vote reject")

    assert game.is_game_over()
    assert game.result == "Spy"


def test_two_fails_required():
    game = ResistanceLogic(8)
    game.make_move(0, "Spy Spy Spy Resistance Resistance Resistance Resistance")

    # Fast forward to round 4 (requires 2 fails)
    game.round = 4
    game.phase = "PROPOSE_SQUAD"

    leader = game.get_current_player()
    assert leader is not None
    assert game.make_move(leader, "propose p1 p2 p3 p4").success

    for i in range(1, 9):
        if i == leader:
            continue
        game.make_move(i, "vote approve")

    assert game.phase == "MISSION_VOTE"

    # p1, p2, p3 are Spies (from DEAL_ROLES)
    # p4 is Resistance (from DEAL_ROLES) -> automatically plays success
    # 1 fail, but 2 required, so mission should succeed
    game.make_move(1, "play sabotage")  # Spy
    game.make_move(2, "play success")  # Spy (playing along)
    game.make_move(3, "play success")  # Spy (playing along)

    assert game.phase == "DISCUSSION_ORDER"
    assert game.score_resistance == 1
    assert game.score_spies == 0
    assert game.completed_missions[0]["sabotage_count"] == 1

    game.make_move(0, "p1 p2 p3 p4 p5 p6 p7 p8")
    for i in range(1, 9):
        game.make_move(i, "Yay")

    assert game.phase == "PROPOSE_SQUAD"
