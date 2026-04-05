from sxpb_game.by_title.mafia.logic import MafiaLogic


def test_day_lynch_tiebreaker():
    game = MafiaLogic(num_players=6)
    game.make_move(0, "Mafia Villager Doctor Detective Villager")

    game.phase = "DAY_VOTE"
    game.alive = [True, True, True, True, True]
    game.vote_order = [0, 1, 2, 3, 4]
    game.vote_idx = 0

    # Votes: p1(vote p2), p2(vote p3), p3(vote p2), p4(vote none), p5(vote p3)
    # p2 and p3 both have 2 votes.
    # p2 was voted for first (by p1). So p2 should die.
    game.make_move(1, "vote p2")
    game.make_move(2, "vote p3")
    game.make_move(3, "vote p2")
    game.make_move(4, "vote none")
    game.make_move(5, "vote p3")

    assert not game.alive[1]  # p2 should be dead
    assert game.alive[2]  # p3 should be alive


def test_day_lynch_tiebreaker_abstain():
    game = MafiaLogic(num_players=6)
    game.make_move(0, "Mafia Villager Doctor Detective Villager")

    game.phase = "DAY_VOTE"
    game.alive = [True, True, True, True, True]
    game.vote_order = [0, 1, 2, 3, 4]
    game.vote_idx = 0

    # Votes: p1(vote none), p2(vote p3), p3(vote none), p4(vote p3), p5(vote p4)
    # none: 2 votes, p3: 2 votes
    # Abstain wins ties
    game.make_move(1, "vote none")
    game.make_move(2, "vote p3")
    game.make_move(3, "vote none")
    game.make_move(4, "vote p3")
    game.make_move(5, "vote p4")

    assert game.alive[2]  # p3 survived


def test_night_kill_tiebreaker():
    game = MafiaLogic(num_players=7)
    game.make_move(0, "Mafia Mafia Villager Villager Villager Villager")

    assert game.phase == "NIGHT_MAFIA_DISCUSSION"
    game.make_move(1, "Let's kill p3")
    game.make_move(2, "No, p4")

    assert game.phase == "NIGHT_MAFIA_VOTE"

    # p1 votes p3, p2 votes p4
    # p3 was voted first, so p3 is the target
    game.make_move(1, "kill p3")
    game.make_move(2, "kill p4")

    # In a game with no Doctor/Detective, it resolves instantly
    assert game.phase == "DAY_ORDER"
    game.make_move(0, "p1 p2 p4 p5 p6")
    assert game.phase == "DAY_DISCUSSION"
    assert not game.alive[2]  # p3 is dead!
    assert game.alive[3]  # p4 is alive
