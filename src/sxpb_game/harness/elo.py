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

from pathlib import Path

import sxpb

K_NEW = 64  # K-factor for models with < 10 games
K_ESTABLISHED = 32
DEFAULT_RATING = 1500
SPREAD = 400  # Rating gap that gives ~0.91 expected score


def _expected_score(ra: float, rb: float) -> float:
    """Expected score for a player rated *ra* against an opponent rated *rb*."""
    return 1.0 / (1.0 + 10.0 ** ((rb - ra) / SPREAD))


def _new_rating(rating: float, expected: float, actual: float, k: float) -> int:
    """Return new ELO rating (rounded to nearest integer)."""
    return round(rating + k * (actual - expected))


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


def update_elo(
    path: str | Path,
    player_results: dict[str, float],
    *,
    k_new: int = K_NEW,
    k_established: int = K_ESTABLISHED,
) -> dict[str, tuple[int, int, int, int]]:
    """Update ELO ratings for a completed game and write back to disk.

    Args:
        path: Path to a per-game ``elo.sxpb`` file.
        player_results: ``{elo_name: score}`` — *score* is 1.0 (win),
            0.5 (draw), or 0.0 (loss).
        k_new: K-factor for models with < 10 games played.
        k_established: K-factor for models with ≥ 10 games.

    Returns:
        ``{elo_name: (old_rating, new_rating, delta, count)}``
        suitable for logging / display.
    """
    path = Path(path)
    ratings = read_elo(path)

    players = list(player_results.keys())
    scores = list(player_results.values())
    n = len(players)

    results: dict[str, tuple[int, int, int, int]] = {}
    new_ratings: dict[str, tuple[int, int]] = {}

    for i, name in enumerate(players):
        old_rating, count = ratings.get(name, (DEFAULT_RATING, 0))

        # Average expected score against every opponent.
        expected_total = 0.0
        opponent_count = 0
        for j in range(n):
            if i == j:
                continue
            opp_rating, _ = ratings.get(players[j], (DEFAULT_RATING, 0))
            expected_total += _expected_score(old_rating, opp_rating)
            opponent_count += 1

        expected = expected_total / opponent_count if opponent_count > 0 else 0.5
        actual = scores[i]
        k = k_new if count < 10 else k_established

        new_rating = _new_rating(old_rating, expected, actual, k)
        new_count = count + 1

        new_ratings[name] = (new_rating, new_count)
        results[name] = (old_rating, new_rating, new_rating - old_rating, new_count)

    # Preserve unmodified entries.
    for name, (rating, count) in ratings.items():
        if name not in new_ratings:
            new_ratings[name] = (rating, count)

    _write_elo(path, new_ratings)
    return results


def _write_elo(path: Path, data: dict[str, tuple[int, int]]) -> None:
    """Write ELO data to a flat SxPB file."""
    path.parent.mkdir(parents=True, exist_ok=True)

    lines = ["()"]
    for model_name in sorted(data):
        rating, count = data[model_name]
        lines.append(f"({model_name} (rating {rating}) (count {count}))")
    lines.append("")

    path.write_text("\n".join(lines))


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
