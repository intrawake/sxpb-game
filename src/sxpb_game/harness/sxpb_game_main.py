import argparse
import ctypes
import importlib
import inspect
import json
import os
import random
import re
import signal
import string
import sys
import textwrap
import threading
import time
import typing
from datetime import datetime, timezone
from pathlib import Path

# Ensure we can import from src and local modules
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from rendezqueue.client import RendezqueueClient
from sxpb_game.eval.logic import GameLogic, OUTCOME_TO_SCORE
from sxpb_llm import (
    load_model_definitions,
    resolve_model,
    parse_sxpb_answer,
)
import sxpb
from sxpb_game.eval.utils import (
    call_api,
    generate_client_prompt,
    generate_prompt,
    get_player_by_identifier_sxpb,
)


def _load_rating_aliases(model_by_name_path: str) -> dict[str, str]:
    """Load rating_alias overrides from a model_by_name.sxpb file.

    Returns a dict mapping alias -> rating_alias string.
    These are game-level metadata that must not reach the API payload.
    """
    try:
        raw = sxpb.loads(Path(model_by_name_path).read_text())
    except Exception:
        return {}
    if not isinstance(raw, dict):
        return {}
    result: dict[str, str] = {}
    for alias, entry in raw.items():
        alias = str(alias)
        if isinstance(entry, dict):
            entry = dict(entry)
            if "rating_alias" in entry:
                result[alias] = str(entry["rating_alias"])
    return result


def format_sxpb_txt(s):
    if s is None:
        return '""'
    if not isinstance(s, str):
        s = str(s)
    if "\n" not in s:
        return json.dumps(s)
    s = s.replace("\\", "\\\\").replace('"""', '""\\"')
    if not s.endswith("\n"):
        return f'"""\\n{s}\\n"""'
    return f'"""\\n{s}"""'


def shuffle_player_configs(player_configs, indices_str, randint_func=None):
    if randint_func is None:
        randint_func = random.randint

    cleaned_str = re.sub(r"\D", " ", indices_str)
    valid_indices = []
    for x in cleaned_str.split():
        idx = int(x)
        if idx >= len(player_configs):
            print(f"Error: --shuffle_players index {idx} out of bounds.")
            sys.exit(1)
        if idx not in valid_indices:
            valid_indices.append(idx)

    for n in range(len(valid_indices)):
        i = valid_indices[n]
        j = valid_indices[randint_func(0, n)]
        player_configs[i], player_configs[j] = player_configs[j], player_configs[i]


def _validate_outcome_player_configs(
    game: GameLogic,
    player_configs: list,
) -> list[int]:
    """Validate and return the outcome-bearing player indices.

    Raises:
        ValueError: If any outcome-bearing player lacks a model, or any
            non-outcome-bearing player is not an algorithm (random).
    """
    indices = game.get_outcome_player_indices()
    if any(not isinstance(i, int) or isinstance(i, bool) for i in indices):
        raise ValueError("outcome player indices must be integers")
    if len(set(indices)) != len(indices):
        raise ValueError("outcome player indices must be unique")
    invalid_indices = [i for i in indices if i < 0 or i >= len(player_configs)]
    if invalid_indices:
        raise ValueError(f"outcome player indices out of range: {invalid_indices}")
    non_model_indices = [
        i
        for i in indices
        if not isinstance(player_configs[i], dict) or "model" not in player_configs[i]
    ]
    if non_model_indices:
        raise ValueError(
            "outcome-bearing players must have models; "
            f"non-model indices: {non_model_indices}"
        )

    # Non-outcome-bearing players must be algorithm (random).
    num_players = len(player_configs)
    all_indices = set(range(num_players))
    non_outcome_indices = sorted(all_indices - set(indices))
    for i in non_outcome_indices:
        conf = player_configs[i]
        if not isinstance(conf, dict) or conf.get("algorithm") != "random":
            raise ValueError(
                f"non-outcome-bearing player at index {i} must be "
                "algorithm random, but is not"
            )

    return indices


def _update_elo_if_configured(
    elo_file: str | None,
    game: GameLogic,
    elo_key_by_player_index: dict[int, str],
) -> None:
    """Compute scores from a completed game's outcomes and update ELO."""
    if not elo_file or not game.is_game_over():
        return

    outcomes = game.get_player_outcomes()
    expected_indices = set(elo_key_by_player_index)
    actual_indices = set(outcomes)
    if actual_indices != expected_indices:
        raise ValueError(
            "completed outcome indices differ from get_outcome_player_indices(): "
            f"expected {sorted(expected_indices)}, got {sorted(actual_indices)}"
        )

    try:
        from sxpb_game.harness.elo import update_elo

        player_elo_results = {
            elo_key_by_player_index[i]: OUTCOME_TO_SCORE[outcome]
            for i, outcome in outcomes.items()
        }
        if len(player_elo_results) < len(outcomes):
            sys.stdout.write(
                "ELO: skipped — multiple players share the same ELO key (self-play).\n"
            )
            return

        deltas = update_elo(elo_file, player_elo_results)
        sys.stdout.write("ELO ratings updated:\n")
        for name, (old, new, delta, count) in deltas.items():
            sign = "+" if delta >= 0 else ""
            sys.stdout.write(
                f"  {name}: {old} → {new} ({sign}{delta})  [{count} games]\n"
            )
        sys.stdout.flush()
    except Exception as e:
        sys.stdout.write(f"Warning: ELO update failed: {e}\n")
        sys.stdout.flush()


def _write_report_sxpb(
    path: str,
    game_name: str,
    game,
    players: list[str],
    player_configs: list[dict],
    *,
    elo_key_by_player_index: dict[int, str] | None = None,
) -> None:
    """Write a unified match report SxPB file.

    Format:
        (report ...)    — metadata message
        <view SxPB>     — existing render_player_full_sxpb(0) output

    When *elo_key_by_player_index* is provided, each player entry
    gets a ``(rating_alias ...)`` field matching the resolved ELO key.
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    outcomes = game.get_player_outcomes()

    player_records = []
    for i, pid in enumerate(players):
        conf = dict(player_configs[i]) if i < len(player_configs) else {}
        outcome = outcomes.get(i)
        conf["id"] = pid
        conf["outcome"] = outcome.value if outcome is not None else "na"
        if elo_key_by_player_index and i in elo_key_by_player_index:
            conf["rating_alias"] = elo_key_by_player_index[i]
        player_records.append(conf)

    report = {
        "game": game_name,
        "timestamp": timestamp,
        "players": player_records,
    }
    header = sxpb.dumps({"report": report})

    view = game.render_player_full_sxpb(0).strip()

    with open(path, "w") as f:
        f.write(header + "\n" + view + "\n")


def main(exit_func=None):
    if exit_func is None:
        exit_func = os._exit

    argv = sys.argv[1:]
    new_argv = []
    i = 0
    while i < len(argv):
        if argv[i] == "--args" and i + 1 < len(argv):
            args_val = argv[i + 1]
            i += 2
            if args_val.strip().startswith("("):
                loaded_args = sxpb.loads(args_val)
            else:
                with open(args_val, "r") as f:
                    loaded_args = sxpb.loads(f.read())
            if not isinstance(loaded_args, list):
                print("Error: --args must parse to a list of strings")
                sys.exit(1)
            new_argv.extend([str(x) for x in loaded_args])
        else:
            new_argv.append(argv[i])
            i += 1

    parser = argparse.ArgumentParser(description="Generic Game Server (Authority)")
    parser.add_argument(
        "--args", help="SxPB string or file defining additional command-line arguments"
    )
    parser.add_argument(
        "--rendezqueue_api_url",
        help="Rendezqueue service URL",
    )
    parser.add_argument("--key", help="Base game key (default: name of the game)")
    parser.add_argument(
        "--game", required=True, help="Name of the game module (e.g. tictactoe)"
    )
    parser.add_argument(
        "--players", help="SxPB string or file defining the player configs"
    )
    parser.add_argument(
        "--shuffle_players",
        help="Permissively formatted string of player indices to shuffle",
    )
    parser.add_argument(
        "--turn_limit",
        type=int,
        help="Maximum number of turns before ending the game inconclusive",
    )
    parser.add_argument(
        "--log_sxpb", help="Filepath to write the full SxPB move history to"
    )
    parser.add_argument(
        "--postgame_on",
        action="store_true",
        help="Prompt the LLMs for post-game analysis",
    )
    parser.add_argument(
        "--trace_jsonl",
        help="Filepath to write the detailed JSONL turn trace to",
    )
    parser.add_argument(
        "--final_view_sxpb",
        help="Filepath to write the final player-0 view of the game (SxPB) to",
    )
    parser.add_argument(
        "--report_sxpb",
        help="Filepath to write the final view SxPB with a (report ...) header",
    )
    parser.add_argument(
        "--elo_sxpb",
        dest="elo_file",
        metavar="FILE",
        help="Path to elo.sxpb for updating ratings at game conclusion",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Enable stdin interactive interface for server management",
    )
    parser.add_argument(
        "--retry_limit",
        type=int,
        default=3,
        help="Maximum number of retries for failed LLM responses",
    )
    parser.add_argument(
        "--model_by_name",
        default=os.path.join(
            os.path.dirname(__file__), "..", "..", "..", "preset", "model_by_name.sxpb"
        ),
        help="SxPB string or file defining model-specific overrides (must start with `()` to parse as a dict)",
    )
    parser.add_argument(
        "--openai_api_url",
        dest="openai_api_url",
        help="OpenAI-compatible API URL (e.g. https://api.openai.com/v1)",
    )
    parser.add_argument(
        "--client_full_prompt_on",
        action="store_true",
        help="Send full LLM-style instructions (rules + format) to clients along with the sxpb view",
    )
    args = parser.parse_args(new_argv)

    if args.key:
        game_key = args.key
    else:
        suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
        game_key = f"{args.game}_{suffix}"

    player_configs = []
    if args.players:
        if args.players.strip().startswith("("):
            player_configs = sxpb.loads(args.players)
            if isinstance(player_configs, dict):
                # If it's a single dict (like (model qwen)), wrap it in a list
                player_configs = [player_configs]
        else:
            with open(args.players, "r") as f:
                player_configs = sxpb.loads(f.read())

        if not isinstance(player_configs, list):
            print("Error: --players must parse to a list (e.g. `(() (model qwen))`)")
            sys.exit(1)

        if args.shuffle_players:
            shuffle_player_configs(player_configs, args.shuffle_players)

    definitions = load_model_definitions(args.model_by_name)
    rating_aliases = _load_rating_aliases(args.model_by_name)

    try:
        try:
            logic_mod = importlib.import_module(f"sxpb_game.by_title.{args.game}.logic")
        except ImportError:
            logic_mod = importlib.import_module(f"{args.game}.logic")
        logic_class = None
        for name, obj in inspect.getmembers(logic_mod, inspect.isclass):
            if issubclass(obj, GameLogic) and obj is not GameLogic:
                logic_class = obj
                break
        if logic_class is None:
            raise ValueError(f"No GameLogic subclass found in {args.game}.logic")
    except Exception as e:
        print(f"Error loading game logic for '{args.game}': {e}")
        sys.exit(1)

    init_kwargs = {}
    if player_configs:
        sig = inspect.signature(logic_class.__init__)
        if "num_players" in sig.parameters:
            init_kwargs["num_players"] = len(player_configs)

    game = logic_class(**init_kwargs)
    game_lock = threading.RLock()
    shutdown_event = threading.Event()
    exit_requested = threading.Event()
    managed_threads: set[threading.Thread] = set()
    managed_threads_lock = threading.Lock()
    turns_taken = 0
    move_history = []

    def start_daemon_thread(target):
        def run():
            try:
                target()
            finally:
                with managed_threads_lock:
                    managed_threads.discard(threading.current_thread())

        thread = threading.Thread(target=run, daemon=True)
        with managed_threads_lock:
            managed_threads.add(thread)
        thread.start()
        return thread

    def get_model_config(conf):
        requested_model = conf.get("model", "gemini-flash-alt2")
        reasoning_effort = conf.get(
            "reasoning_effort", getattr(args, "reasoning_effort", None)
        )
        mc = resolve_model(
            requested_model, definitions, reasoning_effort=reasoning_effort
        )
        api_kwargs = dict(mc.extra)
        # Strip game-level metadata that must not reach the API.
        api_kwargs.pop("rating_alias", None)
        if "temperature" in api_kwargs:
            api_kwargs["temperature"] = float(api_kwargs["temperature"])
        if mc.token_gen_limit != 16384:
            api_kwargs["max_tokens"] = mc.token_gen_limit
        return mc.fullname, mc.reasoning_effort, mc.timeout, api_kwargs

    def write_logs_and_exit(code):
        if args.final_view_sxpb:
            try:
                with game_lock:
                    idx = 0
                    state_sxpb = game.render_player_full_sxpb(idx)
                    history_sxpb = ""

                    visible_indices = getattr(
                        game, "get_visible_players", lambda i: list(range(len(players)))
                    )(idx)
                    players_sxpb = get_player_by_identifier_sxpb(
                        players, player_configs, visible_indices
                    )

                    final_content = ""
                    if players_sxpb:
                        final_content += f"{players_sxpb}\n\n"
                    if history_sxpb:
                        final_content += f"{history_sxpb}\n\n"
                    final_content += f"{state_sxpb}\n"

                    with open(args.final_view_sxpb, "w") as f:
                        f.write(final_content)
            except Exception as e:
                print(f"Failed to write final view log: {e}")

        if args.log_sxpb:
            try:
                with open(args.log_sxpb, "w") as f:
                    f.write("(())\n")
                    for entry in move_history:
                        tag = "turn" if entry["valid"] else "invalid_turn"
                        safe_txt = format_sxpb_txt(entry["content"])
                        f.write(
                            f"({tag} (p {entry['player_index']}) (txt {safe_txt}))\n"
                        )
            except Exception as e:
                print(f"Failed to write history log: {e}")

        if args.trace_jsonl:
            try:
                with open(args.trace_jsonl, "w") as f:
                    for entry in move_history:
                        rec = {
                            "valid": entry.get("valid"),
                            "p": entry.get("player_index"),
                            "txt": entry.get("content"),
                            "prompt": entry.get("prompt"),
                            "response": entry.get("raw_response"),
                            "model": entry.get("model"),
                        }
                        if entry.get("api_request"):
                            rec["api_request"] = entry.get("api_request")
                        if entry.get("api_res"):
                            rec["api_response"] = entry.get("api_res")
                        f.write(json.dumps(rec) + "\n")
            except Exception as e:
                print(f"Failed to write verbose log: {e}")

        exit_requested.set()
        shutdown_event.set()
        exit_func(code)

    sigint_lock = threading.Lock()

    def handle_sigint(signum, frame):
        if not sigint_lock.acquire(blocking=False):
            return
        sys.stdout.write("\nStopping server...\n")
        sys.stdout.flush()
        for c in player_clients.values():
            c.stop()
        write_logs_and_exit(0)

    try:
        signal.signal(signal.SIGINT, handle_sigint)
    except ValueError:
        pass  # In case it is not called from the main thread

    class AbortRequestException(BaseException):
        pass

    server_state: "typing.Dict[str, typing.Any]" = {
        "llm_thread": None,
        "is_suspended": False,
        "suspended_players": {},
        "resumed_players": set(),
    }

    def check_suspension(idx):
        is_player_suspended = (
            idx is not None
            and idx in server_state["suspended_players"]
            and idx not in server_state["resumed_players"]
        )
        is_global = server_state["is_suspended"]
        return is_global or is_player_suspended, is_player_suspended

    def stdin_listener():
        nonlocal turns_taken
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            if line in ("quit", "exit"):
                sys.stdout.write("Exiting server...\n")
                sys.stdout.flush()
                write_logs_and_exit(0)
                return
            elif line == "retry":
                with game_lock:
                    if server_state["llm_thread"]:
                        res = ctypes.pythonapi.PyThreadState_SetAsyncExc(
                            ctypes.c_long(server_state["llm_thread"]),
                            ctypes.py_object(AbortRequestException),
                        )
                        if res == 0:
                            sys.stdout.write("Failed to interrupt LLM thread.\n")
                        else:
                            sys.stdout.write(
                                "Interrupting current LLM request for retry...\n"
                            )
                        sys.stdout.flush()
                    else:
                        sys.stdout.write("No active LLM request to retry.\n")
                        sys.stdout.flush()
            elif line.startswith("suspend"):
                parts = line.split()
                if len(parts) > 1:
                    try:
                        idx = int(parts[1])
                        count = -1
                        if len(parts) > 2:
                            count = int(parts[2])
                        with game_lock:
                            if count == 0:
                                server_state["suspended_players"].pop(idx, None)
                                server_state["resumed_players"].discard(idx)
                                sys.stdout.write(
                                    f"Suspension cleared for Player {idx}.\n"
                                )
                            else:
                                server_state["suspended_players"][idx] = count
                                server_state["resumed_players"].discard(idx)
                                if count == -1:
                                    sys.stdout.write(
                                        f"Game will suspend the next time Player {idx} is about to move.\n"
                                    )
                                else:
                                    sys.stdout.write(
                                        f"Game will suspend the next {count} times Player {idx} is about to move.\n"
                                    )
                    except ValueError:
                        sys.stdout.write(
                            f"Invalid player index or count: {' '.join(parts[1:])}\n"
                        )
                else:
                    with game_lock:
                        server_state["is_suspended"] = True
                    sys.stdout.write("Game will suspend after the current move.\n")
                sys.stdout.flush()
            elif line.startswith("resume"):
                parts = line.split()
                with game_lock:
                    was_suspended = (
                        server_state["is_suspended"]
                        or len(server_state["suspended_players"]) > 0
                    )
                    if len(parts) > 1:
                        try:
                            idx = int(parts[1])
                            if idx in server_state["suspended_players"]:
                                count = server_state["suspended_players"][idx]
                                if count > 0:
                                    server_state["suspended_players"][idx] -= 1
                                    if server_state["suspended_players"][idx] == 0:
                                        del server_state["suspended_players"][idx]
                                elif count == -1:
                                    del server_state["suspended_players"][idx]

                                server_state["resumed_players"].add(idx)
                                sys.stdout.write(f"Resuming Player {idx}...\n")
                            else:
                                sys.stdout.write(f"Player {idx} was not suspended.\n")
                        except ValueError:
                            sys.stdout.write(f"Invalid player index: {parts[1]}\n")
                    else:
                        server_state["is_suspended"] = False
                        current_idx = game.get_current_player()
                        if (
                            current_idx is not None
                            and current_idx in server_state["suspended_players"]
                        ):
                            count = server_state["suspended_players"][current_idx]
                            if count > 0:
                                server_state["suspended_players"][current_idx] -= 1
                                if server_state["suspended_players"][current_idx] == 0:
                                    del server_state["suspended_players"][current_idx]
                            elif count == -1:
                                del server_state["suspended_players"][current_idx]
                            server_state["resumed_players"].add(current_idx)
                        sys.stdout.write("Resuming...\n")

                    if was_suspended:
                        sys.stdout.flush()
                        if not server_state["llm_thread"]:
                            start_daemon_thread(process_automated_turn)
                    else:
                        sys.stdout.write("Game is not suspended.\n")
                        sys.stdout.flush()
            elif line.startswith("view"):
                parts = line.split()
                idx = 0
                if len(parts) > 1:
                    try:
                        idx = int(parts[1])
                    except ValueError:
                        sys.stdout.write(f"Invalid player index: {parts[1]}\n")
                        sys.stdout.flush()
                        continue
                with game_lock:
                    if idx < 0 or idx >= len(players):
                        sys.stdout.write(
                            f"Player index {idx} out of range (0-{len(players) - 1}).\n"
                        )
                    else:
                        sys.stdout.write(
                            f"--- View for Player {idx} ({players[idx]}) ---\n"
                        )
                        sys.stdout.write(
                            game.render_player_full_sxpb(idx).strip() + "\n"
                        )
                        sys.stdout.write("---------------------------\n")
                    sys.stdout.flush()
            elif line == "prompt":
                with game_lock:
                    idx = game.get_current_player()
                    if idx is None:
                        sys.stdout.write("No current player.\n")
                    else:
                        sys.stdout.write(
                            f"--- Prompt for Player {idx} ({players[idx]}) ---\n"
                        )
                        prompt = generate_prompt(game, idx, player_configs)
                        sys.stdout.write(prompt + "\n")
                        sys.stdout.write("---------------------------\n")
                    sys.stdout.flush()
            elif line.startswith("say "):
                parts = line.split(maxsplit=1)
                if len(parts) < 2:
                    sys.stdout.write("Usage: say <move_text>\n")
                    sys.stdout.flush()
                    continue
                move_text = parts[1].strip()
                with game_lock:
                    idx = game.get_current_player()
                    is_suspended, is_player_suspended = check_suspension(idx)
                    if not is_suspended:
                        sys.stdout.write("Game is not suspended.\n")
                        sys.stdout.flush()
                        continue
                    if idx is None:
                        sys.stdout.write("No current player.\n")
                        sys.stdout.flush()
                        continue

                    valid, reason = attempt_move(
                        idx, move_text, prompt="<say command>", raw_response=move_text
                    )
                    if valid:
                        sys.stdout.write(
                            f"Say move accepted for Player {idx}: {move_text}\n"
                        )
                        sys.stdout.flush()
                        turns_taken += 1
                        for p in players:
                            send_state_to_player(p)

                        was_suspended = (
                            server_state["is_suspended"]
                            or len(server_state["suspended_players"]) > 0
                        )
                        server_state["is_suspended"] = False
                        if idx in server_state["suspended_players"]:
                            count = server_state["suspended_players"][idx]
                            if count > 0:
                                server_state["suspended_players"][idx] -= 1
                                if server_state["suspended_players"][idx] == 0:
                                    del server_state["suspended_players"][idx]
                            elif count == -1:
                                del server_state["suspended_players"][idx]
                        sys.stdout.write("Resuming...\n")
                        sys.stdout.flush()

                        if was_suspended:
                            if not server_state["llm_thread"]:
                                start_daemon_thread(process_automated_turn)
                    else:
                        sys.stdout.write(f"Invalid say move '{move_text}': {reason}\n")
                        sys.stdout.flush()
            elif line == "history":
                with game_lock:
                    sys.stdout.write("--- Move History ---\n")
                    for i, entry in enumerate(move_history):
                        tag = "turn" if entry["valid"] else "invalid_turn"
                        if entry.get("is_analysis"):
                            tag = "analysis"
                        sys.stdout.write(
                            f"{i}: (p {entry['player_index']}) [{tag}] {entry['content']}\n"
                        )
                    sys.stdout.write("---------------------------\n")
                    sys.stdout.flush()
            elif line.startswith("premove "):
                parts = line.split(maxsplit=2)
                if len(parts) < 3:
                    sys.stdout.write("Usage: premove <idx> <move_text>\n")
                    sys.stdout.flush()
                    continue
                try:
                    idx = int(parts[1])
                except ValueError:
                    sys.stdout.write(f"Invalid player index: {parts[1]}\n")
                    sys.stdout.flush()
                    continue
                move_text = parts[2].strip()
                with game_lock:
                    if idx < 0 or idx >= len(player_configs):
                        sys.stdout.write(f"Player index {idx} out of range.\n")
                    else:
                        conf = player_configs[idx]
                        if not isinstance(conf, dict):
                            player_configs[idx] = {"premoves": [move_text]}
                        else:
                            if "premoves" not in conf:
                                conf["premoves"] = []
                            conf["premoves"].append(move_text)
                        sys.stdout.write(
                            f"Added premove for Player {idx}: {move_text}\n"
                        )
                    sys.stdout.flush()
            elif line == "help":
                sys.stdout.write("Supported commands:\n")
                sys.stdout.write(
                    "  view [idx]      - Show game view for player [idx] (default 0)\n"
                )
                sys.stdout.write(
                    "  prompt          - Show the prompt for the current player\n"
                )
                sys.stdout.write("  history         - Show the move history\n")
                sys.stdout.write(
                    "  premove <i> <m> - Add a premove <m> for player index <i>\n"
                )
                sys.stdout.write(
                    "  say <m>         - Like premove+resume for current player (only when paused)\n"
                )
                sys.stdout.write(
                    "  retry           - Abort and retry the current LLM request\n"
                )
                sys.stdout.write(
                    "  suspend [idx] [n] - Pause the game (globally or for player [idx] for [n] moves)\n"
                )
                sys.stdout.write(
                    "  resume [idx]    - Resume the game loop (globally or for player [idx])\n"
                )
                sys.stdout.write("  help            - Show this help message\n")
                sys.stdout.write("  quit, exit      - Shut down the server\n")
                sys.stdout.flush()
            else:
                sys.stdout.write(
                    f'Unknown command: {line}. Type "help" for available commands.\n'
                )
                sys.stdout.flush()

    players = game.get_player_identifiers()
    while len(player_configs) < len(players):
        player_configs.append({})

    external_players = []
    for p, conf in zip(players, player_configs):
        if not isinstance(conf, dict) or (
            "model" not in conf and "algorithm" not in conf
        ):
            external_players.append(p)

    if external_players and not args.rendezqueue_api_url:
        print(
            f"Error: --rendezqueue_api_url is required because players {external_players} are expected to connect externally."
        )
        sys.exit(1)

    elo_key_by_player_index: dict[int, str] = {}
    if args.elo_file:
        try:
            outcome_player_indices = _validate_outcome_player_configs(
                game, player_configs
            )
        except ValueError as e:
            print(f"Error: --elo_sxpb {e}")
            sys.exit(1)

        for player_idx in outcome_player_indices:
            conf = player_configs[player_idx]
            model, _, _, _ = get_model_config(conf)
            alias = conf.get("model", "")
            elo_key = model
            if alias and alias in definitions:
                elo_key = rating_aliases.get(alias, model)
            elo_key_by_player_index[player_idx] = elo_key

    if external_players:
        print(
            f"Starting Authoritative Game Server for '{args.game}' on {args.rendezqueue_api_url}"
        )
        print(f"Lobby: {game_key}")
    else:
        print(f"Starting Authoritative Game Server for '{args.game}' (clientless)")

    for p, conf in zip(players, player_configs):
        if "model" in conf:
            print(f"Player {p} managed by LLM: {conf.get('model', 'default')}")
        elif "algorithm" in conf:
            print(f"Player {p} managed by algorithm: {conf['algorithm']}")
        else:
            name = conf.get("name", p)
            p_key = conf.get("key", f"{game_key}_{p}")
            print(
                f"Player {p} ({name}) command: pdm run client --rendezqueue_api_url {args.rendezqueue_api_url} --key {p_key}"
            )

    def attempt_move(
        idx,
        move_str,
        prompt=None,
        raw_response=None,
        api_req=None,
        api_res=None,
        model=None,
    ):
        move_failed_reason = None
        if move_str is None:
            valid = False
            move_failed_reason = "No move was parsed from your response."
        else:
            try:
                res = game.make_move(idx, move_str)
                if isinstance(res, tuple):
                    valid, move_failed_reason = res
                else:
                    valid = res
                    if not valid:
                        move_failed_reason = "Invalid move according to game rules."
            except Exception as e:
                sys.stdout.write(f"Exception in make_move: {e}\n")
                valid = False
                move_failed_reason = f"System error during move: {e}"

        if not valid and move_str and move_failed_reason:
            move_str = f"{move_str} # feedback: {move_failed_reason}"
        move_history.append(
            {
                "player_index": idx,
                "content": move_str,
                "valid": valid,
                "prompt": prompt,
                "raw_response": raw_response,
                "api_request": api_req,
                "api_res": api_res,
                "model": model,
            }
        )
        return valid, move_failed_reason

    def send_state_to_player(player_id):
        with game_lock:
            is_over = game.is_game_over() or (
                args.turn_limit and turns_taken >= args.turn_limit
            )
            winner = getattr(game, "winner", None) if game.is_game_over() else None
            if (
                args.turn_limit
                and turns_taken >= args.turn_limit
                and not game.is_game_over()
            ):
                winner = "Turn limit reached"
            valid_moves = (
                getattr(game, "get_valid_moves", lambda: [])() if not is_over else []
            )
            curr_idx = game.get_current_player()
            state = {
                "board_sxpb": game.render_player_full_sxpb(players.index(player_id)),
                "status": "GAME_OVER" if is_over else "PLAYING",
                "current_player": players[curr_idx] if curr_idx is not None else None,
                "your_player": player_id,
                "winner": winner,
                "valid_moves": valid_moves,
            }
            if getattr(args, "client_full_prompt_on", False):
                player_idx = players.index(player_id)
                state["full_prompt"] = generate_client_prompt(
                    game, player_idx, player_configs
                )
            if player_id in player_clients:
                player_clients[player_id].send(json.dumps(state))
                sys.stdout.write(f"Sent state to Player {player_id}\n")
                sys.stdout.flush()

    def process_automated_turn():
        nonlocal turns_taken
        if exit_requested.is_set():
            return
        with game_lock:
            idx = game.get_current_player()
            is_suspended, is_player_suspended = check_suspension(idx)

            if is_suspended:
                if is_player_suspended:
                    sys.stdout.write(
                        f"Game is suspended for Player {idx}. Use 'resume' to continue.\n"
                    )
                else:
                    sys.stdout.write("Game is suspended. Use 'resume' to continue.\n")
                sys.stdout.flush()
                return

            if idx is not None:
                server_state["resumed_players"].discard(idx)

            if game.is_game_over() or (
                args.turn_limit and turns_taken >= args.turn_limit
            ):
                shutdown_event.set()
                return
            idx = game.get_current_player()
            if idx is None:
                return
            curr_player_id = players[idx]
            conf = player_configs[idx]
            if not isinstance(conf, dict):
                return

            if conf.get("premoves"):
                move = conf["premoves"].pop(0)
                sys.stdout.write(f"Premove used for {curr_player_id}: {move}\n")
                sys.stdout.flush()
                valid, reason = attempt_move(idx, move)
                if valid:
                    turns_taken += 1
                    for p in players:
                        send_state_to_player(p)
                    start_daemon_thread(process_automated_turn)
                else:
                    sys.stdout.write(
                        f"Invalid premove '{move}' for player {curr_player_id}.\n"
                    )
                    sys.stdout.flush()
                    write_logs_and_exit(1)
                return

        if "model" in conf:
            process_llm_turn(idx, curr_player_id, conf)
        elif "algorithm" in conf:
            process_algorithm_turn(idx, curr_player_id, str(conf["algorithm"]))

    def process_algorithm_turn(idx, curr_player_id, algorithm):
        nonlocal turns_taken
        with game_lock:
            move, error = game.get_algorithm_move(idx, algorithm)
            if error:
                sys.stdout.write(f"Algorithm error for {curr_player_id}: {error}\n")
                sys.stdout.flush()
                write_logs_and_exit(1)

            valid, reason = attempt_move(idx, move)
            if move and valid:
                sys.stdout.write(
                    f"Algorithm Move accepted from {curr_player_id}: {move}\n"
                )
                sys.stdout.flush()
                turns_taken += 1
                for p in players:
                    send_state_to_player(p)
                process_automated_turn()
            else:
                if not move:
                    attempt_move(idx, None)
                sys.stdout.write(
                    f"Algorithm provided invalid move '{move}' for player {curr_player_id}.\n"
                )
                sys.stdout.flush()
                write_logs_and_exit(1)

    def process_llm_turn(idx, curr_player_id, conf):
        model, reasoning_effort, req_timeout, api_kwargs = get_model_config(conf)

        if (
            model
            not in [
                "non-existent-model",
                "empty-response-model",
                "invalid-response-model",
                "reject-empty-assistant-model",
            ]
            and not args.openai_api_url
        ):
            sys.stdout.write(
                f"Error: Player {curr_player_id} is an LLM, but --openai_api_url was not provided.\n"
            )
            sys.stdout.flush()
            write_logs_and_exit(1)

        def llm_worker():
            nonlocal turns_taken
            with game_lock:
                prompt = generate_prompt(game, idx, player_configs)
                valid_moves = getattr(game, "get_valid_moves", lambda: [])()
                valid_str = ", ".join(valid_moves) if valid_moves else "Any valid move"

            sys.stdout.write(f"LLM thinking for player {curr_player_id}...\n")
            sys.stdout.flush()

            messages = [{"role": "user", "content": prompt}]
            attempt = 0
            while attempt < args.retry_limit:
                if exit_requested.is_set():
                    return
                with game_lock:
                    server_state["llm_thread"] = threading.get_ident()

                try:
                    if model == "non-existent-model":
                        content, api_req, api_res = None, None, None
                    elif model == "empty-response-model":
                        content, api_req, api_res = (
                            "",
                            {"messages": list(messages)},
                            None,
                        )
                    elif model == "invalid-response-model":
                        content, api_req, api_res = (
                            '```sxpb > /dev/stdout\n(answer "invalid_move_123")\n```',
                            {"messages": list(messages)},
                            None,
                        )
                    elif model == "reject-empty-assistant-model":
                        # Simulates Cohere: returns None (like API 400) when
                        # messages contain an empty assistant, else empty string.
                        has_empty_assistant = any(
                            msg.get("role") == "assistant"
                            and not msg.get("content", "").strip()
                            for msg in messages
                        )
                        if has_empty_assistant:
                            content, api_req, api_res = None, None, None
                        else:
                            content, api_req, api_res = (
                                "",
                                {"messages": list(messages)},
                                None,
                            )
                    else:
                        content, api_req, api_res = call_api(
                            model,
                            messages,
                            timeout=req_timeout,
                            reasoning_effort=reasoning_effort,
                            return_full=True,
                            api_url=args.openai_api_url,
                            **api_kwargs,
                        )
                except AbortRequestException:
                    content, api_req, api_res = None, None, None
                    sys.stdout.write(
                        f"LLM request for {curr_player_id} was aborted by user.\n"
                    )
                    sys.stdout.flush()
                finally:
                    with game_lock:
                        server_state["llm_thread"] = None
                prompt_format = 'using the exact format:\n```sxpb > /dev/stdout\n(answer "your_move")\n```'

                if not content:
                    valid, reason = attempt_move(
                        idx,
                        None,
                        prompt=messages[-1]["content"],
                        model=model,
                        api_req=api_req,
                        api_res=api_res,
                    )
                    sys.stdout.write(
                        f"LLM provided empty response for player {curr_player_id}.\n"
                    )
                    sys.stdout.flush()
                    # Empty response: reset to clean prompt. Wipes any previous
                    # invalid-reply context so the model gets a fresh start.
                    messages = [{"role": "user", "content": prompt}]
                    attempt += 1
                    continue

                move = parse_sxpb_answer(content)

                with game_lock:
                    if game.get_current_player() != idx:
                        return
                    valid, reason = attempt_move(
                        idx,
                        move,
                        prompt=messages[-1]["content"],
                        raw_response=content,
                        api_req=api_req,
                        api_res=api_res,
                        model=model,
                    )
                    if valid:
                        sys.stdout.write(
                            f"LLM Move accepted from {curr_player_id}: {move}\n"
                        )
                        sys.stdout.flush()
                        nonlocal turns_taken
                        turns_taken += 1
                        for p in players:
                            send_state_to_player(p)
                        process_automated_turn()
                        return
                    else:
                        sys.stdout.write(
                            f"LLM provided invalid move for {curr_player_id}. Reason: {reason}\n"
                        )
                        sys.stdout.write(f"RAW CONTENT:\n{content}\n")
                        sys.stdout.flush()
                        if (
                            len(messages) >= 3
                            and messages[-2].get("role") == "assistant"
                            and messages[-2].get("content") == content
                        ):
                            messages = [{"role": "user", "content": prompt}]
                        else:
                            messages.append({"role": "assistant", "content": content})
                            messages.append(
                                {
                                    "role": "user",
                                    "content": f"Move failed: {reason} Please respond with ONLY one of the valid options/indices: {valid_str} {prompt_format}",
                                }
                            )
                        attempt += 1

            if not args.interactive:
                sys.stdout.write(
                    f"LLM Move failed repeatedly for {curr_player_id}. Terminating since not in interactive mode.\n"
                )
                sys.stdout.flush()
                write_logs_and_exit(1)

            sys.stdout.write(
                f"LLM Move failed repeatedly for {curr_player_id}. Waiting for user intervention (type 'retry', 'msg <text>', or 'quit').\n"
            )
            sys.stdout.flush()

            with game_lock:
                server_state["llm_thread"] = threading.get_ident()
            try:
                while not exit_requested.wait(0.5):
                    pass
                return
            except AbortRequestException:
                with game_lock:
                    is_suspended, is_player_suspended = check_suspension(idx)
                    if is_suspended:
                        sys.stdout.write(
                            "LLM aborted, but game is suspended. Type 'resume' to retry.\n"
                        )
                        sys.stdout.flush()
                        return
                sys.stdout.write(
                    f"Resuming LLM request for {curr_player_id} after user intervention.\n"
                )
                sys.stdout.flush()
                process_llm_turn(idx, curr_player_id, conf)
                return
            finally:
                with game_lock:
                    server_state["llm_thread"] = None

        start_daemon_thread(llm_worker)

    def create_on_data(player_id):
        def on_data(values):
            nonlocal game
            nonlocal turns_taken
            shutdown_event.set()
            for v in values:
                try:
                    msg = json.loads(v)
                    action = msg.get("action")

                    if action == "JOIN":
                        sys.stdout.write(f"Player {player_id} joined!\n")
                        sys.stdout.flush()
                        send_state_to_player(player_id)
                        process_automated_turn()

                    elif action == "MOVE":
                        move = msg.get("coord")
                        if getattr(args, "client_full_prompt_on", False) and move:
                            try:
                                parsed = sxpb.loads(move)
                                if isinstance(parsed, dict) and "answer" in parsed:
                                    move = parsed["answer"]
                            except Exception:
                                pass
                        with game_lock:
                            if game.get_current_player() != players.index(player_id):
                                sys.stdout.write(
                                    f"Player {player_id} tried to move out of turn!\n"
                                )
                                sys.stdout.flush()
                                send_state_to_player(player_id)
                                continue

                            valid, reason = attempt_move(players.index(player_id), move)
                            if valid:
                                sys.stdout.write(
                                    f"Move accepted from {player_id}: {move}\n"
                                )
                                sys.stdout.flush()
                                turns_taken += 1
                                for p in players:
                                    send_state_to_player(p)
                                process_automated_turn()
                            else:
                                sys.stdout.write(
                                    f"Invalid move from {player_id}: {move}\n"
                                )
                                sys.stdout.flush()
                                send_state_to_player(player_id)

                except Exception as e:
                    sys.stdout.write(
                        f"Error processing Player {player_id} message: {e}\n"
                    )
                    sys.stdout.flush()

        return on_data

    player_clients = {}
    for p, conf in zip(players, player_configs):
        if "model" not in conf and "algorithm" not in conf:
            p_key = conf.get("key", f"{game_key}_{p}")
            player_clients[p] = RendezqueueClient(
                url=args.rendezqueue_api_url,
                key=p_key,
                hue=f"server_for_{p}",
                on_data=create_on_data(p),
                poll_interval_ms=500,
            )

    try:
        for c in player_clients.values():
            c.start()

        sys.stdout.write("Server is live. Waiting for players on private channels...\n")
        sys.stdout.flush()
        if args.interactive:
            start_daemon_thread(stdin_listener)

        process_automated_turn()

        conclusion_start = None
        while not exit_requested.is_set():
            shutdown_event.wait(timeout=1.0)
            shutdown_event.clear()
            if exit_requested.is_set():
                break

            with game_lock:
                is_over = game.is_game_over() or (
                    args.turn_limit and turns_taken >= args.turn_limit
                )
                if is_over:
                    winner = (
                        getattr(game, "winner", None)
                        if game.is_game_over()
                        else "Turn limit reached"
                    )
                    if (
                        args.turn_limit
                        and turns_taken >= args.turn_limit
                        and not game.is_game_over()
                    ):
                        winner = "Turn limit reached"
                    if conclusion_start is None:
                        conclusion_start = time.time()
                        sys.stdout.write(
                            f"Game concluded (Winner: {winner}). Waiting for players to receive final state...\n"
                        )
                        sys.stdout.flush()

                        # --- ELO update ---
                        _update_elo_if_configured(
                            args.elo_file, game, elo_key_by_player_index
                        )

                    all_received = True
                    for p in players:
                        if p in player_clients:
                            with player_clients[p].lock:
                                if len(player_clients[p].outgoing_queue) > 0:
                                    all_received = False
                                    break

                    if all_received:
                        sys.stdout.write(
                            "All players received final state. Shutting down now.\n"
                        )
                        sys.stdout.flush()
                        break

                    if time.time() - conclusion_start > 15:
                        sys.stdout.write("Shutdown timeout reached. Exiting.\n")
                        sys.stdout.flush()
                        break

        if exit_requested.is_set():
            return

        def ask_llm_for_regrets():
            def regret_worker(idx, p_id, conf):
                model, current_reasoning_effort, req_timeout, api_kwargs = (
                    get_model_config(conf)
                )

                if (
                    model not in ["non-existent-model", "empty-response-model"]
                    and not args.openai_api_url
                ):
                    sys.stdout.write(
                        f"Warning: Skipping post-game analysis for {p_id} because --openai_api_url was not provided.\n"
                    )
                    sys.stdout.flush()
                    return

                with game_lock:
                    state_sxpb = game.render_player_full_sxpb(idx)
                    history_sxpb = ""

                    if history_sxpb:
                        state_sxpb = f"{history_sxpb}\n\n{state_sxpb}"

                    visible_indices = getattr(
                        game, "get_visible_players", lambda i: list(range(len(players)))
                    )(idx)
                    players_sxpb = get_player_by_identifier_sxpb(
                        players, player_configs, visible_indices
                    )
                    winner = getattr(game, "winner", None)

                player_info_section = (
                    "\n"
                    + textwrap.dedent(
                        f"""
                        ### Player Information
                        ```sxpb
                        {players_sxpb}
                        ```
                        """
                    ).strip()
                    + "\n"
                    if players_sxpb
                    else ""
                )
                rules = getattr(game, "get_rules", lambda: "")()
                rules_section = f"\n### Rules\n{rules}\n" if rules else ""
                winner_str = f"\nWinner: {winner}\n" if winner else ""

                prompt = f"""\
You are a playing agent. You played as: {p_id}
The game has concluded.{winner_str}{player_info_section}{rules_section}
### Final Game State (SxPB format)
```sxpb
{state_sxpb}
```

### Instructions
- The game is over. Analyze your play throughout the game.
- Do you have any regrets about your moves or strategy?
- Could you have played better?
"""

                sys.stdout.write(
                    f"Asking LLM player {p_id} for end-of-game analysis...\n"
                )
                sys.stdout.flush()

                content, api_req, api_res = call_api(
                    model,
                    prompt,
                    timeout=req_timeout,
                    reasoning_effort=current_reasoning_effort,
                    return_full=True,
                    api_url=args.openai_api_url,
                    **api_kwargs,
                )

                if content:
                    with game_lock:
                        move_history.append(
                            {
                                "player_index": idx,
                                "valid": True,
                                "is_analysis": True,
                                "content": content,
                                "prompt": prompt,
                                "raw_response": content,
                                "api_req": api_req,
                                "api_res": api_res,
                                "model": model,
                            }
                        )

            for i, conf in enumerate(player_configs):
                if isinstance(conf, dict) and "model" in conf:
                    regret_worker(i, players[i], conf)

        if args.postgame_on:
            ask_llm_for_regrets()

        if args.report_sxpb and game.is_game_over():
            try:
                _write_report_sxpb(
                    args.report_sxpb,
                    args.game,
                    game,
                    players,
                    player_configs,
                    elo_key_by_player_index=elo_key_by_player_index or None,
                )
            except Exception as e:
                print(f"Failed to write report SxPB: {e}")

        if args.final_view_sxpb:
            try:
                with game_lock:
                    idx = 0
                    state_sxpb = game.render_player_full_sxpb(idx)
                    history_sxpb = ""

                    visible_indices = getattr(
                        game, "get_visible_players", lambda i: list(range(len(players)))
                    )(idx)
                    players_sxpb = get_player_by_identifier_sxpb(
                        players, player_configs, visible_indices
                    )

                    final_content = ""
                    if players_sxpb:
                        final_content += f"{players_sxpb}\n\n"
                    if history_sxpb:
                        final_content += f"{history_sxpb}\n\n"
                    final_content += f"{state_sxpb}\n"

                    with open(args.final_view_sxpb, "w") as f:
                        f.write(final_content)
            except Exception as e:
                print(f"Failed to write final view log: {e}")

        if args.log_sxpb:
            with open(args.log_sxpb, "w") as f:
                f.write("(())\n")
                for entry in move_history:
                    if entry.get("is_analysis"):
                        tag = "analysis"
                    else:
                        tag = "turn" if entry["valid"] else "invalid_turn"
                    safe_txt = format_sxpb_txt(entry["content"])
                    f.write(f"({tag} (p {entry['player_index']}) (txt {safe_txt}))\n")

        if args.trace_jsonl:
            with open(args.trace_jsonl, "w") as f:
                for entry in move_history:
                    rec = {
                        "valid": entry.get("valid"),
                        "p": entry.get("player_index"),
                        "txt": entry.get("content"),
                        "prompt": entry.get("prompt"),
                        "response": entry.get("raw_response"),
                        "model": entry.get("model"),
                    }
                    if entry.get("api_req"):
                        rec["api_request"] = entry.get("api_req")
                    if entry.get("api_res"):
                        rec["api_response"] = entry.get("api_res")
                    f.write(json.dumps(rec) + "\n")

    except KeyboardInterrupt:
        pass
    finally:
        exit_requested.set()
        shutdown_event.set()
        for c in player_clients.values():
            c.stop()

        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline:
            with managed_threads_lock:
                threads = [
                    thread
                    for thread in managed_threads
                    if thread is not threading.current_thread()
                ]
            if not threads:
                break
            for thread in threads:
                thread.join(timeout=min(0.05, max(0.0, deadline - time.monotonic())))


if __name__ == "__main__":
    main()
