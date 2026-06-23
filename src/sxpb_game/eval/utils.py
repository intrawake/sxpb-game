import argparse
import pathlib
import re
import sxpb

from sxpb_llm import call_api as _sxpb_llm_call_api


def parse_last_word(content, strict_mode=False, filter_func=str.isalpha):
    if strict_mode:
        return "".join(filter(filter_func, content))
    else:
        tokens = content.split()
        if not tokens:
            return ""
        raw = tokens[-1]
        return "".join(filter(filter_func, raw))


def parse_game_guess(
    content, keyword, answer_regex, strict_mode=False, filter_func=str.isalnum
):
    """Generic parser for game guesses.
    Searches for keyword: answer (optionally markdown bolded) anywhere in content.
    Falls back to parse_last_word of the last line.
    """
    lines = content.strip().splitlines()
    if not lines:
        return None

    # Search bottom-up for "Keyword: answer" (allowing for bolding/whitespace)
    pattern = re.compile(
        rf"{keyword}:\s*({answer_regex})(?:\b|\s|$|(?=[^\w\s]))", re.IGNORECASE
    )

    for line in reversed(lines):
        match = pattern.search(line)
        if match:
            # Clean the answer part (match group 1)
            return "".join(filter(filter_func, match.group(1)))

    # Fallback: parse last word of last line
    return parse_last_word(lines[-1], strict_mode=strict_mode, filter_func=filter_func)


def call_api(
    model,
    prompt,
    *,
    api_url: str,
    timeout=0,
    log_file=None,
    reasoning_effort=None,
    return_full=False,
    **kwargs,
):
    """Thin wrapper around sxpb_llm.call_api for backward compatibility."""
    return _sxpb_llm_call_api(
        model,
        prompt,
        api_url=api_url,
        timeout=timeout,
        log_file=log_file,
        reasoning_effort=reasoning_effort,
        return_full=return_full,
        **kwargs,
    )


def create_base_parser(description):
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "--model", default="gemini-flash-alt2", help="Model name to use"
    )
    parser.add_argument(
        "--openai_api_url",
        dest="openai_api_url",
        required=True,
        help="OpenAI-compatible API URL (e.g. https://api.openai.com/v1)",
    )
    parser.add_argument("--timeout", type=int, default=0, help="API timeout in seconds")
    parser.add_argument(
        "--dry-run", action="store_true", help="Print API request payload and exit"
    )
    parser.add_argument(
        "--print-prompt", action="store_true", help="Print the raw prompt text and exit"
    )
    parser.add_argument(
        "--interactive", action="store_true", help="Play manually on the terminal"
    )
    parser.add_argument(
        "--oneshot",
        action="store_true",
        help="Read guesses from stdin, run one turn, exit",
    )
    parser.add_argument(
        "--reasoning-effort",
        "--reasoning_effort",
        dest="reasoning_effort",
        help="Pass reasoning_effort param to API (e.g. low/medium/high)",
    )
    parser.add_argument(
        "--log", help="Log all API requests and responses to the specified file"
    )
    return parser


SHARED_FIELDS = {"name", "pronoun", "bio"}


def get_player_by_identifier_sxpb(players, player_configs=None, visible_indices=None):
    if not player_configs or not visible_indices:
        return ""

    d = {}
    for i in visible_indices:
        p_id = players[i]
        conf = player_configs[i] if i < len(player_configs) else {}
        p_info = {k: v for k, v in conf.items() if k in SHARED_FIELDS}
        d[p_id] = p_info
    return sxpb.dumps({"player_by_identifier": d}).strip()


def generate_prompt(game, player_idx: int, player_configs=None) -> str:
    """Generates the standard prompt for a given game and player."""
    players = game.get_player_identifiers()
    curr_player_id = players[player_idx]

    state_sxpb = game.render_player_full_sxpb(player_idx)

    visible_indices = getattr(
        game, "get_visible_players", lambda idx: list(range(len(players)))
    )(player_idx)
    players_sxpb = get_player_by_identifier_sxpb(
        players, player_configs, visible_indices
    )
    player_info_section = (
        f"\n### Player Information\n```sxpb\n{players_sxpb}\n```\n"
        if players_sxpb
        else ""
    )

    prompt_q = game.get_prompt(player_idx)
    valid_moves = getattr(game, "get_valid_moves", lambda: [])()
    valid_str = ", ".join(valid_moves) if valid_moves else "Any valid move"

    rules = getattr(game, "get_rules", lambda: "")()
    rules_section = f"\n\n### Rules\n{rules}\n" if rules else ""

    persona_section = ""
    if player_configs and player_idx < len(player_configs):
        persona = player_configs[player_idx].get("persona")
        if persona:
            persona_section = f"\n### Secret Persona\n{persona}\n"

    instruction_path = pathlib.Path(__file__).parent / "instruction.md"
    try:
        instruction_text = instruction_path.read_text(encoding="utf-8")
    except Exception:
        instruction_text = "ERROR: Could not load instruction.md"

    return f"""\
You are a playing agent. You are player: {curr_player_id}
Your goal is to win the game or force a draw.{rules_section}{persona_section}{player_info_section}
### Current Game State (SxPB format)
```sxpb
{state_sxpb}
```

### Instructions
{instruction_text}

Valid indices/moves: {valid_str}

### Question
```sxpb < /dev/stdin
{prompt_q}
```
"""


def generate_client_prompt(game, player_idx: int, player_configs=None) -> str:
    """Generates a prompt for external clients connecting via rendezqueue.

    Same as generate_prompt but replaces the LLM-specific ### Instructions block
    with guidance for using the --move flag with SxPB format.
    """
    players = game.get_player_identifiers()
    curr_player_id = players[player_idx]

    state_sxpb = game.render_player_full_sxpb(player_idx)

    visible_indices = getattr(
        game, "get_visible_players", lambda idx: list(range(len(players)))
    )(player_idx)
    players_sxpb = get_player_by_identifier_sxpb(
        players, player_configs, visible_indices
    )
    player_info_section = (
        f"\n### Player Information\n```sxpb\n{players_sxpb}\n```\n"
        if players_sxpb
        else ""
    )

    prompt_q = game.get_prompt(player_idx)
    valid_moves = getattr(game, "get_valid_moves", lambda: [])()
    valid_str = ", ".join(valid_moves) if valid_moves else "Any valid move"

    rules = getattr(game, "get_rules", lambda: "")()
    rules_section = f"\n\n### Rules\n{rules}\n" if rules else ""

    persona_section = ""
    if player_configs and player_idx < len(player_configs):
        persona = player_configs[player_idx].get("persona")
        if persona:
            persona_section = f"\n### Secret Persona\n{persona}\n"

    return f"""\
You are a playing agent. You are player: {curr_player_id}
Your goal is to win the game or force a draw.{rules_section}{persona_section}{player_info_section}
### Current Game State (SxPB format)
```sxpb
{state_sxpb}
```

### Instructions
To make your move, use the --move flag with your answer as an SxPB string:
  pdm run client ... --move '(answer "<your_move>")'

The server will parse your SxPB answer the same way it parses LLM responses.

Valid indices/moves: {valid_str}

### Question
```sxpb < /dev/stdin
{prompt_q}
```
"""
