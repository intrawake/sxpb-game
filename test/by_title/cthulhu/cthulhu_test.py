from sxpb_game.by_title.cthulhu.logic import CthulhuLogic


def test_cthulhu_random_game():
    game = CthulhuLogic(4)
    assert game.get_player_identifiers() == ["GM", "p1", "p2", "p3", "p4"]

    while not game.is_game_over():
        curr = game.get_current_player()
        if curr is None:
            break
        move, _ = game.get_algorithm_move(curr, "random")
        if move is None:
            break
        success = game.make_move(curr, move)
        assert success

    assert game.winner in ["Investigators", "Cultists"]
