"""One command per turn, with an explicit protocol continuation on clean exit."""

import argparse
import json
import sys
import threading
import time
import uuid

from rendezqueue.client import RendezqueueClient
from rendezqueue.continuation import decode_id


def print_state(state):
    if state.get("status") == "GAME_OVER":
        print("\nFinal Board:")
        print("```sxpb\n" + state.get("board_sxpb", "").strip() + "\n```")
        print(f"Game Over! Winner: {state.get('winner')}")
    elif state.get("full_prompt"):
        print("\n" + state["full_prompt"].strip())
    else:
        print("\nCurrent Board:")
        print("```sxpb\n" + state.get("board_sxpb", "").strip() + "\n```")
        print(f"Status: {state.get('status')}")
        print(f"You are: {state.get('your_player')}")
        print(f"Current Player: {state.get('current_player')}")
        print(f"Valid moves: {', '.join(state.get('valid_moves', []))}")


def main():
    parser = argparse.ArgumentParser(
        description="Generic Game Client (Blocking Oneshot)"
    )
    parser.add_argument(
        "--rendezqueue_api_url", required=True, help="Full Rendezqueue endpoint URL"
    )
    parser.add_argument(
        "--key", required=True, help="Role-specific game key (e.g. lobby_X)"
    )
    parser.add_argument(
        "--move", help="A single move; wait for the next own turn and exit."
    )
    parser.add_argument(
        "--status", action="store_true", help="Wait for own turn/status and exit."
    )
    parser.add_argument(
        "--self",
        dest="self_xid",
        type=decode_id,
        default=b"",
        help="Own XID from the latest continuation line",
    )
    parser.add_argument(
        "--peer",
        dest="peer_xid",
        type=decode_id,
        default=b"",
        help="Peer XID from the same continuation line",
    )
    args = parser.parse_args()
    if bool(args.self_xid) != bool(args.peer_xid):
        parser.error("--self and --peer must be supplied together")
    if args.self_xid and args.self_xid == args.peer_xid:
        parser.error("--self and --peer must differ")

    current_state = None
    join_received = False
    move_result = None
    state_lock = threading.Lock()
    state_event = threading.Event()
    join_id, move_id = uuid.uuid4().hex, uuid.uuid4().hex

    def on_data(values):
        nonlocal current_state, join_received, move_result
        with state_lock:
            for value in values:
                try:
                    state = json.loads(value)
                except (ValueError, UnicodeError):
                    continue
                if not isinstance(state, dict) or "board_sxpb" not in state:
                    continue
                current_state = state
                if state.get("reply_to") == join_id:
                    join_received = True
                if state.get("reply_to") == move_id and isinstance(
                    state.get("accepted"), bool
                ):
                    move_result = state["accepted"]
        state_event.set()

    client = RendezqueueClient(
        url=args.rendezqueue_api_url,
        room=args.key,
        hue="game_client",
        on_data=on_data,
        poll_interval_ms=250,
        continuable=True,
        self_xid=args.self_xid,
        peer_xid=args.peer_xid,
    )
    # Queue before starting; a fresh command always requests a correlated state.
    client.send(json.dumps({"action": "JOIN", "request_id": join_id}))
    client.start()
    try:
        deadline = time.monotonic() + 600
        move_sent = False
        rejected = False
        while True:
            if client.failure is not None:
                raise client.failure
            with state_lock:
                state = current_state
                if join_received and state is not None:
                    if state.get("status") == "GAME_OVER":
                        break
                    own_turn = state.get("current_player") == state.get("your_player")
                    if args.move and not move_sent and own_turn:
                        client.send(
                            json.dumps(
                                {
                                    "action": "MOVE",
                                    "coord": args.move,
                                    "request_id": move_id,
                                }
                            )
                        )
                        move_sent = True
                    elif move_sent and move_result is False:
                        rejected = True
                        break
                    elif move_sent and move_result is True and own_turn:
                        break
                    elif not args.move and own_turn:
                        break
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    "Timeout waiting for game state (600s); no continuation available"
                )
            state_event.wait(timeout=0.25)
            state_event.clear()

        # Certify the peer consumed our last snapshot before dropping this process.
        # Terminal games also need this barrier to seal the last EMPTY receipt.
        continuation = client.finish(timeout=30)
        # finish keeps polling while certifying the handoff. Render the final,
        # quiescent callback state, not a pre-barrier prompt that may be stale.
        with state_lock:
            state = current_state
            assert state is not None
            if state.get("status") == "GAME_OVER":
                rejected = False
        if rejected:
            print("\nServer rejected the move. It is still your turn.")
        else:
            print_state(state)
        if state.get("status") != "GAME_OVER":
            print("Continue with: " + continuation.arguments())
        sys.stdout.flush()
        return 1 if rejected else 0
    except (RuntimeError, TimeoutError, KeyboardInterrupt) as error:
        print(
            f"Client stopped: {error}. No new continuation; do not reuse an old XID pair.",
            file=sys.stderr,
        )
        return 1
    finally:
        client.stop()


if __name__ == "__main__":
    raise SystemExit(main())
