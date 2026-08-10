"""ELO rating system for sxpb-game model-vs-model matches.

Reads/writes a flat ``elo.sxpb`` file keyed by model name::

    ()
    (aistudio/gemma-4-31b-it (rating 1532) (count 12))
    (nvidia/deepseek-ai/deepseek-v4-flash (rating 1510) (count 8))

Each elo.sxpb file is per-game (the path encodes which game).
New models default to 1500.  K-factor is 64 for models with fewer than
10 games, 32 otherwise.
"""

from __future__ import annotations

import os
import sys
import tempfile
from collections.abc import Iterable, Mapping
from pathlib import Path

import sxpb

K_NEW = 64  # K-factor for models with < 10 games
K_ESTABLISHED = 32
DEFAULT_RATING = 1500
SPREAD = 400  # Rating gap that gives ~0.91 expected score


def _expected_score(ra: float, rb: float) -> float:
    """Expected score for a player rated *ra* against an opponent rated *rb*."""
    return 1.0 / (1.0 + 10.0 ** ((rb - ra) / SPREAD))


def _expected_avg(
    ratings: Mapping[str, tuple[int, int]],
    players: list[str],
    i: int,
) -> float:
    """Average expected score of player *i* against every other player."""
    old_rating, _ = ratings.get(players[i], (DEFAULT_RATING, 0))
    opponent_count = len(players) - 1
    if opponent_count <= 0:
        return 0.5
    total = 0.0
    for j, opp in enumerate(players):
        if i == j:
            continue
        opp_rating, _ = ratings.get(opp, (DEFAULT_RATING, 0))
        total += _expected_score(old_rating, opp_rating)
    return total / opponent_count


def _pairwise_adjustments(
    ratings: Mapping[str, tuple[int, int]],
    players: list[str],
    scores: list[float],
) -> list[float]:
    """Per-player pre-K rating adjustments for a pure win/loss team game.

    Winner i:  (1/(n-1)) · Σ_{j ∈ losers} (1 - E(i,j))     [≥ 0]
    Loser  i:  -(1/(n-1)) · Σ_{j ∈ winners} E(i,j)         [≤ 0]

    Same-team pairs contribute nothing.  This is the pairwise formula
    proven in ``demo-lean4/elo-validity/Pairwise.lean``: winners never
    lose, losers never gain, and the table stays zero-sum (per cross pair,
    the winner's gain and loser's loss cancel by reciprocity).  The
    1/(n-1) scale makes 1v1 exactly standard Elo and bounds every
    per-player delta by the K-factor.
    """
    n = len(players)
    winners = [i for i, s in enumerate(scores) if s == 1.0]
    losers = [i for i, s in enumerate(scores) if s == 0.0]
    scale = 1.0 / (n - 1)
    adjustments = [0.0] * n
    for i in winners:
        ri, _ = ratings.get(players[i], (DEFAULT_RATING, 0))
        total = sum(
            1.0 - _expected_score(ri, ratings.get(players[j], (DEFAULT_RATING, 0))[0])
            for j in losers
        )
        adjustments[i] = scale * total
    for i in losers:
        ri, _ = ratings.get(players[i], (DEFAULT_RATING, 0))
        total = sum(
            _expected_score(ri, ratings.get(players[j], (DEFAULT_RATING, 0))[0])
            for j in winners
        )
        adjustments[i] = -scale * total
    return adjustments


def read_elo(path: str | Path) -> dict[str, tuple[int, int]]:
    """Read a per-game elo.sxpb file.

    Returns:
        ``{model_name: (rating, count)}``.  An empty dict if the file
        does not exist.
    """
    path = Path(path)
    if not path.exists():
        return {}

    raw = sxpb.loads(path.read_text())
    if not isinstance(raw, dict):
        return {}

    result: dict[str, tuple[int, int]] = {}
    for model_name, entry in raw.items():
        model_name = str(model_name)
        if isinstance(entry, dict):
            entry = dict(entry)
            rating = int(entry.get("rating", DEFAULT_RATING))
            count = int(entry.get("count", 0))
        else:
            rating = DEFAULT_RATING
            count = 0
        result[model_name] = (rating, count)

    return result


def apply_elo(
    ratings: Mapping[str, tuple[int, int]],
    player_results: Mapping[str, float],
    *,
    k_new: int = K_NEW,
    k_established: int = K_ESTABLISHED,
) -> tuple[
    dict[str, tuple[int, int]],
    dict[str, tuple[int, int, int, int]],
]:
    """Apply one completed match to an in-memory rating state.

    Returns ``(new_ratings, deltas)`` without mutating *ratings*.

    Pure win/loss games use the pairwise formula (winners never lose;
    ``demo-lean4/elo-validity/Pairwise.lean``); games involving draws keep
    the opponent-averaging behavior.
    """
    players = list(player_results)
    scores = list(player_results.values())
    n = len(players)
    winners = sum(1 for s in scores if s == 1.0)
    drawers = sum(1 for s in scores if s == 0.5)
    pure_win_loss = drawers == 0 and 0 < winners < n
    adjustments = (
        _pairwise_adjustments(ratings, players, scores) if pure_win_loss else None
    )

    results: dict[str, tuple[int, int, int, int]] = {}
    new_ratings = dict(ratings)

    for i, name in enumerate(players):
        old_rating, count = ratings.get(name, (DEFAULT_RATING, 0))
        k = k_new if count < 10 else k_established

        if pure_win_loss:
            assert adjustments is not None
            delta = k * adjustments[i]
        else:
            expected = _expected_avg(ratings, players, i)
            delta = k * (scores[i] - expected)

        new_rating = round(old_rating + delta)
        new_count = count + 1
        new_ratings[name] = (new_rating, new_count)
        results[name] = (old_rating, new_rating, new_rating - old_rating, new_count)

    return new_ratings, results


def replay_elo(
    matches: Iterable[Mapping[str, float]],
    *,
    k_new: int = K_NEW,
    k_established: int = K_ESTABLISHED,
) -> dict[str, tuple[int, int]]:
    """Build a fresh rating state by replaying ordered match results."""
    ratings: dict[str, tuple[int, int]] = {}
    for player_results in matches:
        ratings, _ = apply_elo(
            ratings,
            player_results,
            k_new=k_new,
            k_established=k_established,
        )
    return ratings


def update_elo(
    path: str | Path,
    player_results: dict[str, float],
    *,
    k_new: int = K_NEW,
    k_established: int = K_ESTABLISHED,
) -> dict[str, tuple[int, int, int, int]]:
    """Update ELO ratings for a completed game and write back to disk."""
    path = Path(path)
    ratings = read_elo(path)
    scores = list(player_results.values())
    winners = sum(1 for score in scores if score == 1.0)
    drawers = sum(1 for score in scores if score == 0.5)

    if drawers == 0 and 0 < winners < len(scores):
        sys.stdout.write(
            f"ELO: team game (n={len(scores)}, w={winners}), "
            "pairwise deltas (winners never lose)\n"
        )

    new_ratings, results = apply_elo(
        ratings,
        player_results,
        k_new=k_new,
        k_established=k_established,
    )
    write_elo(path, new_ratings)
    return results


def write_elo(
    path: str | Path,
    data: Mapping[str, tuple[int, int]],
) -> None:
    """Atomically write ELO data to a flat SxPB file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    model_names = sorted(data, key=lambda name: (-data[name][0], name))
    lines = ["()"]
    for model_name in model_names:
        rating, count = data[model_name]
        lines.append(f"({model_name} (rating {rating}) (count {count}))")
    lines.append("")
    content = "\n".join(lines)

    file_mode = path.stat().st_mode & 0o777 if path.exists() else 0o644
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            dir=path.parent,
            prefix=f".{path.name}.",
            delete=False,
        ) as temp_file:
            temp_file.write(content)
            temp_path = Path(temp_file.name)
        os.chmod(temp_path, file_mode)
        os.replace(temp_path, path)
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()


def format_leaderboard(
    data: dict[str, tuple[int, int]],
    top: int = 10,
) -> str:
    """Return a formatted leaderboard string."""
    if not data:
        return "No ratings yet."

    sorted_models = sorted(data.items(), key=lambda x: x[1][0], reverse=True)

    lines = ["=== ELO Leaderboard ==="]
    for i, (name, (rating, count)) in enumerate(sorted_models[:top], 1):
        bar_len = min(10, max(0, (rating - 1400) // 20))
        bar = "█" * bar_len + "░" * (10 - bar_len)
        lines.append(f" {i:2d}.  {name:<45s} {rating:4d}  {bar}  {count:2d} games")

    return "\n".join(lines)
