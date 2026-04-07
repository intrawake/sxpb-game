import sys
import os
import json
import time
import argparse
import threading
import importlib
import inspect
import typing

# Ensure we can import from src and local modules
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from rendezqueue.client import RendezqueueClient
from game_eval.logic import GameLogic
import sxpb
from game_eval.utils import call_api, generate_prompt, get_player_by_identifier_sxpb


def format_sxpb_txt(s):
    if s is None:
        return '""'
    if not isinstance(s, str):
        s = str(s)
    if "\n" not in s:
        import json

        return json.dumps(s)
    s = s.replace("\\", "\\\\").replace('"""', '""\\"')
    if not s.endswith("\n"):
        return f'"""\\n{s}\\n"""'
    return f'"""\\n{s}"""'


def main():
    parser = argparse.ArgumentParser(description="Generic Game Server (Authority)")
    parser.add_argument(
        "--rendezqueue_api_url",
        default="https://rendezqueue.com/tryswap",
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
        "--verbose_log_jsonl",
        help="Filepath to write the detailed JSONL turn history to",
    )
    parser.add_argument(
        "--final_view_sxpb",
        help="Filepath to write the final player-0 view of the game (SxPB) to",
    )
    parser.add_argument(
        "--model_by_name",
        default=os.path.join(
            os.path.dirname(__file__), "..", "preset", "model_by_name.sxpb"
        ),
        help="SxPB string or file defining model-specific overrides (must start with `()` to parse as a dict)",
    )
    parser.add_argument(
        "--openai_api_url",
        dest="openai_api_url",
        required=True,
        help="OpenAI-compatible API URL (e.g. https://api.openai.com/v1)",
    )
    args = parser.parse_args()

    import random
    import string

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

    model_overrides = {}
    if args.model_by_name:
        if args.model_by_name.strip().startswith("("):
            model_overrides = sxpb.loads(args.model_by_name)
        else:
            with open(args.model_by_name, "r") as f:
                model_overrides = sxpb.loads(f.read())
        if not isinstance(model_overrides, dict):
            print("Warning: --model_by_name must parse to a dict, ignoring.")
            model_overrides = {}

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
    turns_taken = 0
    move_history = []

    def get_model_config(conf):
        requested_model = conf.get("model", "gemini-flash-alt2")
        reasoning_effort = conf.get(
            "reasoning_effort", getattr(args, "reasoning_effort", None)
        )
        req_timeout = 0

        model = requested_model
        api_kwargs = {}

        if isinstance(requested_model, str):
            if requested_model in model_overrides:
                m_over = model_overrides[requested_model]
                if isinstance(m_over, str):
                    model = m_over
                elif isinstance(m_over, dict):
                    api_kwargs = dict(m_over)
                    if "fullname" in api_kwargs:
                        model = api_kwargs.pop("fullname")
            else:
                for m_name, m_over in model_overrides.items():
                    if (
                        isinstance(m_over, dict)
                        and m_over.get("fullname") == requested_model
                    ):
                        model = m_name
                        api_kwargs = dict(m_over)
                        if "fullname" in api_kwargs:
                            api_kwargs.pop("fullname")
                        break

        if "temperature" in api_kwargs:
            api_kwargs["temperature"] = float(api_kwargs["temperature"])
        if "reasoning_effort" in api_kwargs:
            reasoning_effort = api_kwargs.pop("reasoning_effort")
        if "timeout" in api_kwargs:
            req_timeout = int(api_kwargs.pop("timeout"))

        return model, reasoning_effort, req_timeout, api_kwargs

    def write_logs_and_exit(code):
        if args.final_view_sxpb:
            try:
                with game_lock:
                    idx = 0
                    state_sxpb = game.render_player_view(idx).strip()
                    history_sxpb = getattr(game, "render_player_history", lambda i: "")(
                        idx
                    ).strip()

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

        if args.verbose_log_jsonl:
            try:
                with open(args.verbose_log_jsonl, "w") as f:
                    for entry in move_history:
                        rec = {
                            "valid": entry.get("valid"),
                            "p": entry.get("player_index"),
                            "txt": entry.get("content"),
                            "prompt": entry.get("prompt"),
                            "response": entry.get("raw_response"),
                        }
                        if entry.get("api_req"):
                            rec["api_request"] = entry.get("api_req")
                        if entry.get("api_res"):
                            rec["api_response"] = entry.get("api_res")
                        f.write(json.dumps(rec) + "\n")
            except Exception as e:
                print(f"Failed to write verbose log: {e}")

        os._exit(code)

    import signal

    def handle_sigint(signum, frame):
        signal.signal(signal.SIGINT, signal.SIG_IGN)
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
            elif line == "retry":
                with game_lock:
                    if server_state["llm_thread"]:
                        import ctypes

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
                            threading.Thread(
                                target=process_automated_turn, daemon=True
                            ).start()
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
                        sys.stdout.write(game.render_player_view(idx).strip() + "\n")
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
                                threading.Thread(
                                    target=process_automated_turn, daemon=True
                                ).start()
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

    print(
        f"Starting Authoritative Game Server for '{args.game}' on {args.rendezqueue_api_url}"
    )
    print(f"Lobby: {game_key}")
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
        idx, move_str, prompt=None, raw_response=None, api_req=None, api_res=None
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
                "board_sxpb": game.render_player_view(players.index(player_id)),
                "status": "GAME_OVER" if is_over else "PLAYING",
                "current_player": players[curr_idx] if curr_idx is not None else None,
                "your_player": player_id,
                "winner": winner,
                "valid_moves": valid_moves,
            }
            if player_id in player_clients:
                player_clients[player_id].send(json.dumps(state))
                sys.stdout.write(f"Sent state to Player {player_id}\n")
                sys.stdout.flush()

    def process_automated_turn():
        nonlocal turns_taken
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
                    threading.Thread(target=process_automated_turn, daemon=True).start()
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
            while attempt < 3:
                with game_lock:
                    server_state["llm_thread"] = threading.get_ident()

                try:
                    if model == "non-existent-model":
                        content, api_req, api_res = None, None, None
                    elif model == "empty-response-model":
                        content, api_req, api_res = "", None, None
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
                if not content:
                    valid, reason = attempt_move(
                        idx, None, prompt=messages[-1]["content"]
                    )
                    sys.stdout.write(
                        f"LLM provided empty response for player {curr_player_id}.\n"
                    )
                    sys.stdout.flush()
                    messages.append({"role": "assistant", "content": ""})
                    messages.append(
                        {
                            "role": "user",
                            "content": f'Received empty response. {reason} Please respond with ONLY one of the valid options/indices: {valid_str} using the format `(answer "your_move")`.',
                        }
                    )
                    attempt += 1
                    continue

                move = None
                for line_part in reversed(content.strip().splitlines()):
                    line_part = line_part.strip("` \t;")
                    if (
                        line_part.startswith("(answer ")
                        or line_part.startswith('(answer"')
                    ) and line_part.endswith(")"):
                        try:
                            parsed = sxpb.loads(line_part)
                            if isinstance(parsed, dict) and "answer" in parsed:
                                move = parsed["answer"]
                                break
                        except Exception:
                            inner = (
                                line_part[8:-1].strip()
                                if line_part.startswith("(answer ")
                                else line_part[7:-1].strip()
                            )
                            move = (
                                inner[1:-1]
                                if (
                                    len(inner) >= 2
                                    and inner.startswith('"')
                                    and inner.endswith('"')
                                )
                                else inner
                            )
                            break

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
                        sys.stdout.flush()
                        messages.append({"role": "assistant", "content": content})
                        messages.append(
                            {
                                "role": "user",
                                "content": f'Move failed: {reason} Please respond with ONLY one of the valid options/indices: {valid_str} using the format `(answer "your_move")`.',
                            }
                        )
                        attempt += 1

            sys.stdout.write(
                f"LLM Move failed repeatedly for {curr_player_id}. Waiting for user intervention (type 'retry', 'msg <text>', or 'quit').\n"
            )
            sys.stdout.flush()

            with game_lock:
                server_state["llm_thread"] = threading.get_ident()
            try:
                while True:
                    import time

                    time.sleep(0.5)
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

        threading.Thread(target=llm_worker, daemon=True).start()

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
        threading.Thread(target=stdin_listener, daemon=True).start()

        process_automated_turn()

        conclusion_start = None
        while True:
            shutdown_event.wait(timeout=1.0)
            shutdown_event.clear()

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

        def ask_llm_for_regrets():
            def regret_worker(idx, p_id, conf):
                model, current_reasoning_effort, req_timeout, api_kwargs = (
                    get_model_config(conf)
                )

                with game_lock:
                    state_sxpb = game.render_player_view(idx).strip()
                    history_sxpb = getattr(game, "render_player_history", lambda i: "")(
                        idx
                    ).strip()

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
                    f"\n### Player Information\n```sxpb\n{players_sxpb}\n```\n"
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
                            }
                        )

            for i, conf in enumerate(player_configs):
                if isinstance(conf, dict) and "model" in conf:
                    regret_worker(i, players[i], conf)

        if args.postgame_on:
            ask_llm_for_regrets()

        if args.final_view_sxpb:
            try:
                with game_lock:
                    idx = 0
                    state_sxpb = game.render_player_view(idx).strip()
                    history_sxpb = getattr(game, "render_player_history", lambda i: "")(
                        idx
                    ).strip()

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

        if args.verbose_log_jsonl:
            with open(args.verbose_log_jsonl, "w") as f:
                for entry in move_history:
                    rec = {
                        "valid": entry.get("valid"),
                        "p": entry.get("player_index"),
                        "txt": entry.get("content"),
                        "prompt": entry.get("prompt"),
                        "response": entry.get("raw_response"),
                    }
                    if entry.get("api_req"):
                        rec["api_request"] = entry.get("api_req")
                    if entry.get("api_res"):
                        rec["api_response"] = entry.get("api_res")
                    f.write(json.dumps(rec) + "\n")

    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
