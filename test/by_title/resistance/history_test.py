import sxpb

from sxpb_game.by_title.resistance.logic import ResistanceLogic


def test_history_is_parseable_with_quotes_and_revealed_votes():
    game = ResistanceLogic(num_players=6)
    game.teams = ["Spy", "Resistance", "Resistance", "Spy", "Resistance"]

    game.phase = "DISCUSSION_REPLY"
    game.discussion_target = 0
    assert game.make_move(1, 'I heard "Spy".').success

    game.phase = "VOTE_ON_SQUAD"
    game.proposed_squad = [0, 1]
    for player_idx in range(1, 6):
        assert game.make_move(player_idx, "vote approve").success

    rendered_history = game.render_player_history(1)
    assert '(p1 "I heard \\"Spy\\".")' in rendered_history

    history = sxpb.loads(rendered_history)
    assert isinstance(history, dict)
