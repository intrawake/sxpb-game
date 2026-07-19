import stat
from pathlib import Path

import pytest

from sxpb_game.eval.logic import GameLogic, Outcome
from sxpb_game.harness.elo import read_elo, replay_elo, update_elo, write_elo
from sxpb_game.harness.sxpb_game_main import (
    _update_elo_if_configured,
    _validate_outcome_player_configs,
)


MATCHES = [
    {"alpha": 1.0, "beta": 0.0},
    {"beta": 1.0, "gamma": 0.0},
    {"alpha": 0.5, "gamma": 0.5},
]


class OutcomeIndexGame(GameLogic):
    def __init__(
        self,
        outcome_player_indices: list[int],
        outcomes: dict[int, Outcome] | None = None,
    ):
        self.outcome_player_indices = outcome_player_indices
        self.outcomes = outcomes or {}

    def get_player_identifiers(self) -> list[str]:
        return ["admin", "p1", "p2"]

    def get_outcome_player_indices(self) -> list[int]:
        return self.outcome_player_indices

    def get_player_outcomes(self) -> dict[int, Outcome]:
        return self.outcomes

    def is_game_over(self) -> bool:
        return True


def test_validate_outcome_players_allows_algorithm_administrator():
    game = OutcomeIndexGame([1, 2])
    configs = [
        {"algorithm": "random"},
        {"model": "alpha"},
        {"model": "beta"},
    ]

    assert _validate_outcome_player_configs(game, configs) == [1, 2]


def test_validate_outcome_players_rejects_algorithm_player():
    game = OutcomeIndexGame([1, 2])
    configs = [
        {"algorithm": "random"},
        {"algorithm": "random"},
        {"model": "beta"},
    ]

    with pytest.raises(ValueError, match="non-model indices: \\[1\\]"):
        _validate_outcome_player_configs(game, configs)


def test_validate_outcome_players_rejects_non_outcome_model_player():
    """Non-outcome-bearing player with a model (not algorithm random) is rejected."""
    game = OutcomeIndexGame([1, 2])
    configs = [
        {"model": "admin-model"},
        {"model": "alpha"},
        {"model": "beta"},
    ]

    with pytest.raises(ValueError, match="non-outcome-bearing player at index 0"):
        _validate_outcome_player_configs(game, configs)


def test_validate_outcome_players_rejects_non_outcome_unconfigured_player():
    """Non-outcome-bearing player with no config at all is rejected."""
    game = OutcomeIndexGame([1, 2])
    configs = [
        {},
        {"model": "alpha"},
        {"model": "beta"},
    ]

    with pytest.raises(ValueError, match="non-outcome-bearing player at index 0"):
        _validate_outcome_player_configs(game, configs)


@pytest.mark.parametrize("indices", [[1, 1], [-1, 2], [1, 3], [True, 2]])
def test_validate_outcome_players_rejects_invalid_indices(indices: list[int]):
    game = OutcomeIndexGame(indices)
    configs = [
        {"algorithm": "random"},
        {"model": "alpha"},
        {"model": "beta"},
    ]

    with pytest.raises(ValueError):
        _validate_outcome_player_configs(game, configs)


def test_update_configured_elo_uses_declared_outcomes(tmp_path: Path):
    elo_path = tmp_path / "elo.sxpb"
    game = OutcomeIndexGame(
        [1, 2],
        {1: Outcome.WIN, 2: Outcome.LOSS},
    )

    _update_elo_if_configured(
        str(elo_path),
        game,
        {1: "alpha", 2: "beta"},
    )

    assert read_elo(elo_path) == {"alpha": (1532, 1), "beta": (1468, 1)}


def test_update_configured_elo_rejects_outcome_index_drift(tmp_path: Path):
    elo_path = tmp_path / "elo.sxpb"
    game = OutcomeIndexGame([1, 2], {0: Outcome.WIN, 1: Outcome.LOSS})

    with pytest.raises(ValueError, match="completed outcome indices differ"):
        _update_elo_if_configured(
            str(elo_path),
            game,
            {1: "alpha", 2: "beta"},
        )

    assert not elo_path.exists()


def test_replay_matches_sequential_updates(tmp_path: Path):
    elo_path = tmp_path / "elo.sxpb"
    for match in MATCHES:
        update_elo(elo_path, match)

    assert replay_elo(MATCHES) == read_elo(elo_path)


def test_write_elo_orders_by_descending_rating(tmp_path: Path):
    elo_path = tmp_path / "elo.sxpb"

    write_elo(
        elo_path,
        {"alpha": (1490, 2), "charlie": (1510, 1), "beta": (1510, 3)},
    )

    assert elo_path.read_text().splitlines()[1:] == [
        "(beta (rating 1510) (count 3))",
        "(charlie (rating 1510) (count 1))",
        "(alpha (rating 1490) (count 2))",
    ]


def test_write_elo_replaces_complete_file(tmp_path: Path):
    elo_path = tmp_path / "elo.sxpb"
    elo_path.write_text("stale partial data")
    elo_path.chmod(0o640)

    write_elo(elo_path, {"beta": (1490, 2), "alpha": (1510, 2)})

    assert stat.S_IMODE(elo_path.stat().st_mode) == 0o640
    assert (
        elo_path.read_text()
        == """\
()
(alpha (rating 1510) (count 2))
(beta (rating 1490) (count 2))
"""
    )
