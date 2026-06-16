def test_battleship_game_over_reveal() -> None:
    """At game-over, both players see unredacted history and revealed opponent board."""
    from sxpb_game.by_title.battleship.logic import BattleshipLogic

    game = BattleshipLogic()

    # p1: place ships
    for m in [
        "place carrier a1 h",
        "place battleship f1 h",
        "place cruiser a3 h",
        "place submarine a6 h",
        "place destroyer a8 h",
    ]:
        game.make_move(0, m)
    # p2: place ships
    for m in [
        "place carrier a1 v",
        "place battleship a6 v",
        "place cruiser c1 v",
        "place submarine f1 v",
        "place destroyer h1 v",
    ]:
        game.make_move(1, m)

    # Premove sequence through to game-over (p1 wins)
    moves = [
        (0, "fire a1 a2 a3 a4 a5"),  # p1 sinks carrier
        (1, "fire b1 g1 b3 b6"),  # p2 fires (4 shots after losing carrier)
        (0, "fire a6 a7 a8 a9 b1"),  # p1 sinks battleship
        (1, "fire h1 i1 b8"),  # p2 fires (3 shots)
        (0, "fire c1 c2 c3 c4 c5"),  # p1 sinks cruiser
        (1, "fire j1 j4"),  # p2 fires (2 shots)
        (0, "fire f1 f2 f3 f4 f5"),  # p1 sinks submarine
        (1, "fire e1"),  # p2 fires (1 shot)
        (0, "fire h1 h2 g1 g2 i1"),  # p1 sinks destroyer -> game over
    ]
    for player_idx, fire in moves:
        result = game.make_move(player_idx, fire)
        assert result.success, f"Move {fire!r} by p{player_idx + 1} failed"

    assert game.is_game_over()
    assert game.winner == "p1"

    # Both players see the same unredacted history
    hist_p1 = game.render_player_history(0)
    hist_p2 = game.render_player_history(1)
    assert hist_p1 == hist_p2, (
        "History should be identical for both players at game-over"
    )
    assert "[redacted]" not in hist_p1, (
        "History should not redact placement moves at game-over"
    )

    # p2 (loser) sees p1's ships on the opponent board
    view_p2 = game.render_player_view(1)
    # The opponent board should contain ship letters (not just X/o/.)
    opponent_section = view_p2.split("; Opponent's Board")[1]
    # Ship abbreviations should appear in the revealed board
    for abbr in [" A ", " B ", " C ", " S ", " D "]:
        assert abbr in opponent_section, (
            f"Loser's opponent board should reveal ship {abbr!r} at game-over"
        )

    # Sanity: p2 lost all ships, p1 still has all 5
    assert "ally_ships (()) )" in view_p2 or "ally_ships (()) none" in view_p2
    assert (
        "opponent_ships (()) carrier battleship cruiser submarine destroyer" in view_p2
    )
