import sys
import os
import json
import time
import argparse
import threading

# Ensure we can import from src and local modules
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from rendezqueue.client import RendezqueueClient


def main():
    parser = argparse.ArgumentParser(
        description="Generic Game Client (Blocking Oneshot)"
    )
    parser.add_argument(
        "--rendezqueue_api_url",
        help="Rendezqueue service URL",
    )
    parser.add_argument(
        "--key", required=True, help="Role-specific game key (e.g. lobby_X or lobby_O)"
    )
    parser.add_argument(
        "--move",
        help="A single move to make (e.g. 'a1'). Blocks until opponent responds.",
    )
    parser.add_argument(
        "--status", action="store_true", help="Just wait for turn/status and exit."
    )
    args = parser.parse_args()

    if not args.rendezqueue_api_url:
        print("Error: --rendezqueue_api_url is required for the client to connect.")
        sys.exit(1)

    # The key provided MUST be the role-specific key (lobby_X or lobby_O)
    player_key = args.key

    current_state = None
    state_lock = threading.Lock()
    state_event = threading.Event()

    def on_data(values):
        nonlocal current_state
        for v in values:
            try:
                # The Rendezqueue values are the raw strings sent by the server
                new_state = json.loads(v)
                with state_lock:
                    current_state = new_state
                state_event.set()
            except json.JSONDecodeError:
                pass

    client = RendezqueueClient(
        url=args.rendezqueue_api_url,
        key=player_key,
        hue="game_client",
        on_data=on_data,
        poll_interval_ms=500,
    )

    client.start()

    # Join game (sent to server via our private channel)
    # The server uses the JOIN action to trigger the first state broadcast
    client.send(json.dumps({"action": "JOIN"}))

    try:
        start_time = time.time()
        move_sent = False
        waiting_for_next_turn = False
        last_board_sxpb = None

        while True:
            # Check state
            with state_lock:
                if current_state:
                    status = current_state.get("status")
                    curr_player = current_state.get("current_player")
                    my_player = current_state.get("your_player")

                    # 1. Handle Game Over
                    if status == "GAME_OVER":
                        sys.stdout.write("\nFinal Board:\n")
                        sys.stdout.write(
                            "```sxpb\n"
                            + current_state.get("board_sxpb", "").strip()
                            + "\n```\n"
                        )
                        sys.stdout.write(
                            f"Game Over! Winner: {current_state.get('winner')}\n"
                        )
                        sys.stdout.flush()
                        break

                    # 2. Handle Move Request
                    if args.move and not move_sent:
                        if curr_player == my_player:
                            move = args.move
                            client.send(json.dumps({"action": "MOVE", "coord": move}))
                            move_sent = True
                            waiting_for_next_turn = True
                            # After sending the move, we wait for one more state update
                            # that confirms the move was made. We save the old board to check
                            # if the state actually changed.
                            last_board_sxpb = current_state.get("board_sxpb")
                            current_state = None
                            continue
                        else:
                            # Opponent's turn, we keep waiting for our turn
                            pass

                    # 3. Handle Status Request or Turn Transition
                    elif not move_sent:
                        if curr_player == my_player:
                            sys.stdout.write("\nCurrent Board:\n")
                            sys.stdout.write(
                                "```sxpb\n"
                                + current_state.get("board_sxpb", "").strip()
                                + "\n```\n"
                            )
                            sys.stdout.write(f"Status: {status}\n")
                            sys.stdout.write(f"You are: {my_player}\n")
                            sys.stdout.write(f"Current Player: {curr_player}\n")
                            sys.stdout.write(
                                f"Valid moves: {', '.join(current_state.get('valid_moves'))}\n"
                            )
                            sys.stdout.flush()
                            break

                    # 4. If we sent a move, check if it was accepted
                    elif move_sent:
                        if waiting_for_next_turn:
                            if curr_player != my_player:
                                waiting_for_next_turn = False
                                current_state = None
                                continue
                            elif last_board_sxpb != current_state.get("board_sxpb"):
                                # Single-player or multi-turn games where turn didn't change
                                # but the board state did change, meaning move was accepted.
                                waiting_for_next_turn = False
                                continue
                            else:
                                sys.stdout.write(
                                    "\nServer rejected the move. It is still your turn.\n"
                                )
                                sys.stdout.flush()
                                sys.exit(1)
                        else:
                            if curr_player == my_player:
                                sys.stdout.write("\nCurrent Board:\n")
                                sys.stdout.write(
                                    "```sxpb\n"
                                    + current_state.get("board_sxpb", "").strip()
                                    + "\n```\n"
                                )
                                sys.stdout.write(f"Status: {status}\n")
                                sys.stdout.write(f"You are: {my_player}\n")
                                sys.stdout.write(f"Current Player: {curr_player}\n")
                                sys.stdout.write(
                                    f"Valid moves: {', '.join(current_state.get('valid_moves'))}\n"
                                )
                                sys.stdout.flush()
                                break

            # Global timeout for safety
            if time.time() - start_time > 600:
                sys.stdout.write("Timeout waiting for game state (600s).\n")
                sys.stdout.flush()
                break

            # Wait for an update or timeout to re-check
            state_event.wait(timeout=1.0)
            state_event.clear()

    except (KeyboardInterrupt, EOFError):
        sys.stdout.write("\nExiting...\n")
        sys.stdout.flush()
    finally:
        client.stop()


if __name__ == "__main__":
    main()
