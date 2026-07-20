"""Rebuild a game's ELO file from report messages on stdin.

Input is an SxPB list whose items are the values of ``(report ...)`` messages::

    (())
    (() (game tictactoe) (timestamp "2026-07-10T21:40:13Z") (players ...))
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

import sxpb
from sxpb_llm.model import load_model_definitions

from sxpb_game.harness.elo import format_leaderboard, replay_elo, write_elo

OUTCOME_TO_SCORE: dict[str, float] = {"win": 1.0, "draw": 0.5, "loss": 0.0}


def _parse_timestamp(value: object, report_index: int) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"report {report_index}: timestamp must be a string")
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as e:
        raise ValueError(
            f"report {report_index}: timestamp must be UTC YYYY-MM-DDTHH:MM:SSZ"
        ) from e


def _resolve_elo_name(player: object, definitions: dict, report_index: int) -> str:
    if not isinstance(player, dict):
        raise ValueError(f"report {report_index}: player must be a message")
    alias = player.get("model")
    if not isinstance(alias, str) or not alias:
        raise ValueError(f"report {report_index}: player model must be a string")

    # Report-level rating_alias takes precedence over definitions.
    report_alias = player.get("rating_alias")
    if isinstance(report_alias, str) and report_alias:
        return report_alias

    # Fall back to definitions lookup.
    model_config = definitions.get(alias)
    if model_config is None:
        raise ValueError(f"report {report_index}: unknown model alias {alias!r}")
    elo_name = str(model_config.extra.get("rating_alias", model_config.fullname))
    if not elo_name:
        raise ValueError(
            f"report {report_index}: empty rating alias for model {alias!r}"
        )
    return elo_name


def parse_report_matches(
    text: str,
    expected_game: str,
    definitions: dict,
) -> list[dict[str, float]]:
    """Parse, validate, and chronologically order report messages."""
    try:
        loaded = sxpb.loads(text)
    except Exception as e:
        raise ValueError(f"stdin is not valid SxPB: {e}") from e
    if not isinstance(loaded, list):
        raise ValueError("stdin must be an SxPB list of report messages")
    if not loaded:
        raise ValueError("stdin contains no report messages")

    ordered_matches: list[tuple[datetime, int, dict[str, float]]] = []
    for report_index, report in enumerate(loaded, 1):
        if not isinstance(report, dict):
            raise ValueError(f"report {report_index}: must be a message")
        if report.get("game") != expected_game:
            raise ValueError(
                f"report {report_index}: expected game {expected_game!r}, "
                f"got {report.get('game')!r}"
            )
        timestamp = _parse_timestamp(report.get("timestamp"), report_index)

        players = report.get("players")
        if not isinstance(players, list) or len(players) < 2:
            raise ValueError(
                f"report {report_index}: players must contain at least 2 items"
            )

        player_results: dict[str, float] = {}
        for player_index, player in enumerate(players, 1):
            if not isinstance(player, dict):
                raise ValueError(
                    f"report {report_index}: player {player_index} must be a message"
                )
            outcome = player.get("outcome")
            if outcome == "na":
                continue
            if not isinstance(outcome, str) or outcome not in OUTCOME_TO_SCORE:
                raise ValueError(
                    f"report {report_index}: player {player_index} has unsupported "
                    f"outcome {outcome!r}"
                )
            elo_name = _resolve_elo_name(player, definitions, report_index)
            if elo_name in player_results:
                raise ValueError(
                    f"report {report_index}: multiple players resolve to ELO name "
                    f"{elo_name!r}"
                )
            player_results[elo_name] = OUTCOME_TO_SCORE[outcome]

        if len(player_results) < 2:
            raise ValueError(
                f"report {report_index}: must contain at least 2 outcome-bearing "
                "model players"
            )
        ordered_matches.append((timestamp, report_index, player_results))

    ordered_matches.sort(key=lambda item: (item[0], item[1]))
    return [match for _, _, match in ordered_matches]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="recalculate-elo",
        description="Rebuild an ELO file from an SxPB list of report messages on stdin.",
    )
    parser.add_argument("--game", required=True, help="Expected game title")
    parser.add_argument(
        "--model_by_name",
        required=True,
        help="SxPB model alias definitions",
    )
    parser.add_argument("--output", required=True, help="Destination elo.sxpb path")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        definitions = load_model_definitions(args.model_by_name)
        matches = parse_report_matches(sys.stdin.read(), args.game, definitions)
        ratings = replay_elo(matches)
        write_elo(Path(args.output), ratings)
    except (OSError, RuntimeError, ValueError) as e:
        parser.error(str(e))

    print(f"Replayed {len(matches)} reports into {args.output}")
    print(format_leaderboard(ratings, top=len(ratings)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
