from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
import sxpb

from sxpb_game.tool.recalculate_elo import main, parse_report_matches


DEFINITIONS = {
    "model-a": SimpleNamespace(fullname="provider/a", extra={}),
    "model-b": SimpleNamespace(
        fullname="provider/b-versioned", extra={"elo_name": "provider/b"}
    ),
}


def _input(reports: list[dict]) -> str:
    return sxpb.dumps(reports)


def _report(timestamp: str, first_outcome: str = "win") -> dict:
    second_outcome = "loss" if first_outcome == "win" else "win"
    return {
        "game": "tictactoe",
        "timestamp": timestamp,
        "players": [
            {"model": "model-a", "outcome": first_outcome},
            {"model": "model-b", "outcome": second_outcome},
        ],
    }


def test_parse_rejects_malformed_sxpb():
    with pytest.raises(ValueError, match="stdin is not valid SxPB"):
        parse_report_matches("not sxpb", "tictactoe", DEFINITIONS)


def test_parse_ignores_non_outcome_administrator():
    report = _report("2026-07-11T01:00:00Z")
    report["players"].insert(0, {"algorithm": "random", "outcome": "na"})

    assert parse_report_matches(_input([report]), "tictactoe", DEFINITIONS) == [
        {"provider/a": 1.0, "provider/b": 0.0}
    ]


def test_parse_resolves_aliases_and_sorts_by_timestamp():
    matches = parse_report_matches(
        _input(
            [
                _report("2026-07-11T02:00:00Z", "loss"),
                _report("2026-07-11T01:00:00Z", "win"),
            ]
        ),
        "tictactoe",
        DEFINITIONS,
    )

    assert matches == [
        {"provider/a": 1.0, "provider/b": 0.0},
        {"provider/a": 0.0, "provider/b": 1.0},
    ]


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda report: report.update(game="connect_four"), "expected game"),
        (
            lambda report: report["players"][0].update(outcome="pending"),
            "unsupported outcome",
        ),
        (
            lambda report: report["players"][0].update(model="unknown"),
            "unknown model alias",
        ),
        (
            lambda report: report["players"][1].update(model="model-a"),
            "multiple players resolve",
        ),
    ],
)
def test_parse_rejects_invalid_reports(mutate, message):
    report = _report("2026-07-11T01:00:00Z")
    mutate(report)

    with pytest.raises(ValueError, match=message):
        parse_report_matches(_input([report]), "tictactoe", DEFINITIONS)


def test_parse_rejects_fewer_than_two_outcome_players():
    report = _report("2026-07-11T01:00:00Z")
    report["players"][0] = {"algorithm": "random", "outcome": "na"}

    with pytest.raises(ValueError, match="at least 2 outcome-bearing"):
        parse_report_matches(_input([report]), "tictactoe", DEFINITIONS)


def test_main_does_not_touch_output_when_report_is_invalid(tmp_path: Path):
    output = tmp_path / "elo.sxpb"
    output.write_text("keep me\n")
    invalid_input = _input([_report("not-a-timestamp")])

    with (
        patch(
            "sxpb_game.tool.recalculate_elo.load_model_definitions",
            return_value=DEFINITIONS,
        ),
        patch("sys.stdin", StringIO(invalid_input)),
        pytest.raises(SystemExit),
    ):
        main(
            [
                "--game",
                "tictactoe",
                "--model_by_name",
                "models.sxpb",
                "--output",
                str(output),
            ]
        )

    assert output.read_text() == "keep me\n"
