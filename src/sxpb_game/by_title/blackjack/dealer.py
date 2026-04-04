import os
import sys
import json
import random
import argparse

# Configuration
SUITS = ["S", "H", "D", "C"]
VALUES = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
STATE_FILE = "/tmp/blackjack_state.json"


def get_full_deck():
    return [f"{s}{v}" for s in SUITS for v in VALUES]


def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            pass
    return {"used": []}


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)


def cmd_reset(args):
    if os.path.exists(STATE_FILE):
        os.remove(STATE_FILE)
    print("Deck reshuffled.")


def cmd_draw(args):
    state = load_state()
    used = set(state.get("used", []))
    full_deck = get_full_deck()

    available = [c for c in full_deck if c not in used]

    count = args.count
    if len(available) < count:
        print(
            f"Error: Not enough cards left in the deck! (Requested {count}, Available {len(available)})",
            file=sys.stderr,
        )
        sys.exit(1)

    drawn = []
    for _ in range(count):
        card = random.choice(available)
        available.remove(card)
        drawn.append(card)
        used.add(card)

    # Update state
    state["used"] = list(used)
    save_state(state)

    print(" ".join(drawn))


def main():
    parser = argparse.ArgumentParser(description="Blackjack Dealer")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Reset command
    subparsers.add_parser("reset", help="Reshuffle the deck")

    # Draw command
    draw_parser = subparsers.add_parser("draw", help="Draw cards")
    draw_parser.add_argument(
        "count", type=int, nargs="?", default=1, help="Number of cards to draw"
    )

    args = parser.parse_args()

    if args.command == "reset":
        cmd_reset(args)
    elif args.command == "draw":
        cmd_draw(args)


if __name__ == "__main__":
    main()
