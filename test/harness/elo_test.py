import stat
from pathlib import Path

from sxpb_game.harness.elo import read_elo, replay_elo, update_elo, write_elo


MATCHES = [
    {"alpha": 1.0, "beta": 0.0},
    {"beta": 1.0, "gamma": 0.0},
    {"alpha": 0.5, "gamma": 0.5},
]


def test_replay_matches_sequential_updates(tmp_path: Path):
    elo_path = tmp_path / "elo.sxpb"
    for match in MATCHES:
        update_elo(elo_path, match)

    assert replay_elo(MATCHES) == read_elo(elo_path)


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
