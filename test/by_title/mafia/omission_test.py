from sxpb_game.by_title.mafia.logic import MafiaLogic


def test_doctor_omitted_goes_to_detective():
    game = MafiaLogic(num_players=6)
    assert game.make_move(0, "Mafia Villager Villager Detective Vigilante").success

    assert game.phase == "NIGHT_MAFIA_DISCUSSION"
    assert game.make_move(1, "let's kill p2").success
    assert game.phase == "NIGHT_MAFIA_VOTE"
    assert game.make_move(1, "kill p2").success

    # Doctor is omitted, should go to Detective
    assert game.phase == "NIGHT_DETECTIVE", (
        f"Phase is {game.phase} instead of NIGHT_DETECTIVE"
    )
    assert game.get_current_player() == 4
    assert game.make_move(4, "investigate p1").success

    # Then to Vigilante
    assert game.phase == "NIGHT_VIGILANTE", (
        f"Phase is {game.phase} instead of NIGHT_VIGILANTE"
    )
    assert game.get_current_player() == 5
    assert game.make_move(5, "shoot p3").success

    assert game.phase == "DAY_ORDER"


def test_doctor_and_detective_omitted_goes_to_vigilante():
    game = MafiaLogic(num_players=6)
    assert game.make_move(0, "Mafia Villager Villager Villager Vigilante").success

    assert game.phase == "NIGHT_MAFIA_DISCUSSION"
    assert game.make_move(1, "let's kill p2").success
    assert game.phase == "NIGHT_MAFIA_VOTE"
    assert game.make_move(1, "kill p2").success

    # Doctor and Detective omitted, should go to Vigilante
    assert game.phase == "NIGHT_VIGILANTE", (
        f"Phase is {game.phase} instead of NIGHT_VIGILANTE"
    )
    assert game.get_current_player() == 5
    assert game.make_move(5, "shoot p3").success

    assert game.phase == "DAY_ORDER"


def test_all_specials_omitted():
    game = MafiaLogic(num_players=6)
    assert game.make_move(0, "Mafia Villager Villager Villager Villager").success

    assert game.phase == "NIGHT_MAFIA_DISCUSSION"
    assert game.make_move(1, "let's kill p2").success
    assert game.phase == "NIGHT_MAFIA_VOTE"
    assert game.make_move(1, "kill p2").success

    # No specials, resolves night
    assert game.phase == "DAY_ORDER", f"Phase is {game.phase} instead of DAY_ORDER"


def test_dead_specials_are_skipped():
    game = MafiaLogic(num_players=6)
    assert game.make_move(0, "Mafia Villager Doctor Detective Vigilante").success

    # Kill the Doctor during the first day so they are dead on night 2
    game.alive[2] = False  # Kill Doctor (p3)

    assert game.phase == "NIGHT_MAFIA_DISCUSSION"
    assert game.make_move(1, "let's kill p2").success
    assert game.phase == "NIGHT_MAFIA_VOTE"
    assert game.make_move(1, "kill p2").success

    # Doctor is dead, should skip to Detective
    assert game.phase == "NIGHT_DETECTIVE", (
        f"Phase is {game.phase} instead of NIGHT_DETECTIVE"
    )
    assert game.make_move(4, "investigate p1").success

    assert game.phase == "NIGHT_VIGILANTE", (
        f"Phase is {game.phase} instead of NIGHT_VIGILANTE"
    )
    assert game.make_move(5, "shoot p2").success

    assert game.phase == "DAY_ORDER"
