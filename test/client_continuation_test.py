"""Control the callback that arrives between command result and handoff."""

import json

from rendezqueue.continuation import Continuation
from sxpb_game.harness import client as game_client


def test_terminal_update_during_finish_supersedes_old_turn_prompt(monkeypatch, capsys):
    instances = []

    class Client:
        def __init__(self, *, on_data, **kwargs):
            self.on_data = on_data
            self.failure = None
            self.stopped = False
            instances.append(self)

        def send(self, value):
            self.join_id = json.loads(value)["request_id"]

        def start(self):
            self.on_data(
                [
                    json.dumps(
                        {
                            "board_sxpb": "old board",
                            "status": "PLAYING",
                            "current_player": "X",
                            "your_player": "X",
                            "reply_to": self.join_id,
                            "full_prompt": "OLD TURN PROMPT",
                        }
                    ).encode()
                ]
            )

        def finish(self, timeout):
            self.on_data(
                [
                    json.dumps(
                        {
                            "board_sxpb": "final board",
                            "status": "GAME_OVER",
                            "winner": "X",
                            "your_player": "X",
                            "current_player": None,
                        }
                    ).encode()
                ]
            )
            return Continuation(b"next-own", b"next-peer")

        def stop(self):
            self.stopped = True

    monkeypatch.setattr(game_client, "RendezqueueClient", Client)
    monkeypatch.setattr(
        "sys.argv",
        [
            "client",
            "--rendezqueue_api_url",
            "http://example/",
            "--key",
            "game_X",
            "--status",
        ],
    )
    assert game_client.main() == 0
    output = capsys.readouterr().out
    assert "final board" in output and "Game Over! Winner: X" in output
    assert "OLD TURN PROMPT" not in output and "Continue with:" not in output
    assert instances[0].stopped
