from sxpb_game.by_title.mafia.logic import MafiaLogic


def test_mafia_logic():
    game = MafiaLogic(num_players=6)

    # Init
    assert game.phase == "DEAL_ROLES"
    assert game.get_current_player() == 0

    # Deal roles
    assert game.make_move(0, "Mafia Villager Doctor Detective Villager").success
    assert game.phase == "NIGHT_MAFIA_DISCUSSION"

    # p1 is Mafia. Should be their turn to discuss.
    assert game.get_current_player() == 1

    # Test selective history before discussion
    h1 = game.render_player_history(1)
    assert "((event night_falls))" in h1

    # Mafia discusses
    assert game.make_move(1, "Let's kill p5").success

    assert game.phase == "NIGHT_MAFIA_VOTE"
    assert game.get_current_player() == 1

    # Mafia votes to kill p5
    assert game.make_move(1, "kill p5").success

    # Now Doctor's turn (p3)
    assert game.phase == "NIGHT_DOCTOR"
    assert game.get_current_player() == 3

    # Doctor saves p5
    assert game.make_move(3, "save p5").success

    # Detective's turn (p4)
    assert game.phase == "NIGHT_DETECTIVE"
    assert game.get_current_player() == 4

    # Detective investigates p1
    assert game.make_move(4, "investigate p1").success

    # Night resolves
    assert game.phase == "DAY_ORDER"
    game.make_move(0, "p1 p2 p3 p4 p5")
    assert game.phase == "DAY_DISCUSSION"
    assert game.alive[4]  # p5 was saved

    # Check history filtering
    h_villager = game.render_player_history(2)
    assert 'p1 "Let\'s kill p5"' not in h_villager
    assert "; Mafia" not in h_villager
    assert "Mafia_kill_decision" not in h_villager
    assert "; Doctor" not in h_villager
    assert "; Detective" not in h_villager

    h_mafia = game.render_player_history(1)
    assert '(p1 "Let\'s kill p5")' in h_mafia
    assert '(p1 "kill p5")' in h_mafia
    assert "((event mafia_kill_decision) p5)" in h_mafia
    assert "; Doctor" not in h_mafia

    h_det = game.render_player_history(4)
    assert 'p1 "Let\'s kill p5"' not in h_det
    assert '(p4 "investigate p1")  ; Detective result Mafia' in h_det
    assert "; Mafia" not in h_det
    assert "Mafia_kill_decision" not in h_det

    print("All tests passed!")


def test_day_lynch_tiebreaker():
    game = MafiaLogic(num_players=6)
    game.make_move(0, "Mafia Villager Doctor Detective Villager")

    # Skip to day 1 vote to test voting logic directly
    game.phase = "DAY_VOTE"
    game.alive = [True, True, True, True, True]
    game.vote_order = [0, 1, 2, 3, 4]
    game.vote_idx = 0

    # Votes: p1(vote p2), p2(vote p3), p3(vote p2), p4(vote none), p5(vote p3)
    # p2 and p3 both have 2 votes.
    # p2 was voted for first (by p1). So p2 should die.
    assert game.make_move(1, "vote p2").success
    assert game.make_move(2, "vote p3").success
    assert game.make_move(3, "vote p2").success
    assert game.make_move(4, "vote none").success
    assert game.make_move(5, "vote p3").success

    # p2 should be dead
    assert not game.alive[1]
    assert game.alive[2]


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
    assert game.make_move(1, "vote none").success
    assert game.make_move(2, "vote p3").success
    assert game.make_move(3, "vote none").success
    assert game.make_move(4, "vote p3").success
    assert game.make_move(5, "vote p4").success

    assert game.alive[2]  # p3 survived
    assert "((event no_lynch))" in game.history[-2:]


def test_night_kill_tiebreaker():
    game = MafiaLogic(num_players=7)
    # 2 mafia, p1 and p2
    game.make_move(0, "Mafia Mafia Villager Villager Villager Villager")

    # Needs to go through discussion phase first to set up properly
    # p1 and p2 are mafia
    assert game.phase == "NIGHT_MAFIA_DISCUSSION"
    assert game.make_move(1, "let's kill p3").success
    assert game.make_move(2, "no, let's kill p4").success

    assert game.phase == "NIGHT_MAFIA_VOTE"

    # p1 votes p3, p2 votes p4
    # p3 was voted first, so p3 is the target
    assert game.make_move(1, "kill p3").success
    assert game.make_move(2, "kill p4").success

    # Since there's no doctor/detective, night resolves immediately.
    assert not game.alive[2]  # p3 is dead
    assert game.alive[3]  # p4 is alive


if __name__ == "__main__":
    test_mafia_logic()


def test_team_visibility():
    game = MafiaLogic(num_players=6)
    game.make_move(0, "Mafia Villager Doctor Detective Villager")

    # Kill the Doctor (p3)
    game.alive[2] = False

    # Check view for alive Villager (p2)
    view_p2 = game.render_player_view(2)
    assert "(p3 (status dead) (team Villager))" in view_p2

    # Check that the role is NOT visible
    p3_line = [line for line in view_p2.split("\n") if "(p3" in line][0]
    assert "(role Doctor)" not in p3_line

    # Game over
    game.game_over = True
    view_p2_end = game.render_player_view(2)
    p3_line_end = [line for line in view_p2_end.split("\n") if "(p3" in line][0]

    # Both team and role should be visible now
    assert "(team Villager)" in p3_line_end
    assert "(role Doctor)" in p3_line_end


def test_detective_sees_investigated_team():
    import sxpb
    from typing import cast, Any
    from sxpb_game.by_title.mafia.logic import MafiaLogic

    game = MafiaLogic(num_players=6)
    game.make_move(0, "Mafia Villager Doctor Detective Villager")
    game.make_move(1, "Let's kill p5")
    game.make_move(1, "kill p5")
    game.make_move(3, "save p5")
    game.make_move(4, "investigate p1")  # Detective investigates p1 (Mafia)
    game.make_move(0, "p1 p2 p3 p4 p5")  # Day order

    # Verify Detective view via SxPB
    det_view_str = game.render_player_view(4)
    det_view = cast(Any, sxpb.loads(det_view_str))

    assert det_view["table"]["players"]["p1"].get("team") == "Mafia", (
        "Detective should see p1's team"
    )

    # Verify Villager view via SxPB (should NOT see the team)
    vil_view_str = game.render_player_view(2)
    vil_view = cast(Any, sxpb.loads(vil_view_str))

    assert "team" not in vil_view["table"]["players"]["p1"], (
        "Villager should NOT see p1's team"
    )


def test_doctor_consecutive_saves():
    from sxpb_game.by_title.mafia.logic import MafiaLogic

    game = MafiaLogic(num_players=6)
    game.make_move(0, "Mafia Villager Doctor Detective Villager")

    # Night 1
    # Mafia
    game.make_move(1, "let's kill p5")
    game.make_move(1, "kill p5")

    # Doctor (p3)
    assert game.phase == "NIGHT_DOCTOR"
    assert game.make_move(3, "save p5").success

    # Detective (p4)
    game.make_move(4, "investigate p1")

    # Day 1 - Day Order
    game.make_move(0, "p1 p2 p3 p4 p5")

    # Skip to voting to quickly resolve Day 1
    game.phase = "DAY_VOTE"
    game.vote_order = [0, 1, 2, 3, 4]
    game.vote_idx = 0
    game.make_move(1, "vote none")
    game.make_move(2, "vote none")
    game.make_move(3, "vote none")
    game.make_move(4, "vote none")
    game.make_move(5, "vote none")

    # Night 2
    assert game.phase == "NIGHT_MAFIA_DISCUSSION"
    game.make_move(1, "let's kill p5 again")
    game.make_move(1, "kill p5")

    # Doctor (p3)
    assert game.phase == "NIGHT_DOCTOR"
    # Should not be able to save p5 again
    result = game.make_move(3, "save p5")
    assert not result.success, (
        "Doctor should not be able to save the same player on consecutive nights"
    )
