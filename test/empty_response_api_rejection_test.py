"""Test empty response retry with API rejection of empty assistant messages.

Some APIs (notably Cohere) reject requests that include empty assistant messages
in the conversation history with a 400 error. The current retry logic appends an
empty assistant message before the correction prompt, which causes this.

This test verifies the fix: never include empty assistant messages in the retry
history, even when the model returns empty content.
"""

import os
import subprocess
import sys
import tempfile
import time
import json

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SERVER_PY = os.path.join(REPO_ROOT, "src", "sxpb_game", "harness", "sxpb_game_main.py")


def test_empty_response_with_api_rejection():
    """
    Models that reject empty assistant messages (like Cohere) cause a cycle:
      1. Model returns empty.
      2. Code appends empty assistant + correction.
      3. API rejects with 400 (content=None).
      4. Guard detects pattern, resets to clean prompt.
      5. Model returns empty again -> repeat.

    With retry_limit=6, this burns retries in pairs and may exhaust all retries
    before the model produces valid output.

    The fix: simply do NOT append the empty assistant message. Just add the
    correction as a user message. This prevents API rejection entirely.
    """
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{REPO_ROOT}:{os.path.join(REPO_ROOT, 'src')}"

    # Mock model that simulates Cohere's behavior:
    # - Returns "" (model had nothing to say) if no empty assistant in history
    # - Returns None (simulates API 400 rejection) if empty assistant is present
    players_sxpb = (
        "(()) "
        '(() (name "Bot1") (model "reject-empty-assistant-model")) '
        '(() (name "Bot2") (algorithm "random"))'
    )
    model_by_name_sxpb = '() ("reject-empty-assistant-model" (timeout 1))'

    with tempfile.TemporaryDirectory() as tmp_dir:
        history_file = os.path.join(tmp_dir, "history.sxpb")
        verbose_file = os.path.join(tmp_dir, "verbose.jsonl")

        cmd = [
            sys.executable,
            SERVER_PY,
            "--openai_api_url",
            "http://localhost:0/v1",  # dummy, not used by mock
            "--interactive",
            "--game",
            "tictactoe",
            "--retry_limit",
            "8",
            "--players",
            players_sxpb,
            "--model_by_name",
            model_by_name_sxpb,
            "--rendezqueue_api_url",
            "http://localhost:0/",  # dummy URL
            "--log_sxpb",
            history_file,
            "--verbose_log_jsonl",
            verbose_file,
        ]

        proc = subprocess.Popen(
            cmd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.PIPE,
            text=True,
            cwd=REPO_ROOT,
        )
        time.sleep(5)
        try:
            assert proc.stdin is not None
            proc.stdin.write("quit\n")
            proc.stdin.flush()
            stdout_output, _ = proc.communicate(timeout=10)
        except Exception:
            proc.kill()
            stdout_output, _ = proc.communicate()

        print("Captured Output:")
        print(stdout_output)

        # We expect the harness to reach retry_limit without getting stuck
        # in an infinite loop. Empty responses count should be >= retry_limit
        # (each retry logs "LLM provided empty response").
        empty_count = stdout_output.count("LLM provided empty response")
        api_error_count = stdout_output.count("API Error (400)")

        print(f"\nEmpty response count: {empty_count}")
        print(f"API error (400) count: {api_error_count}")

        # The bug: empty assistant messages in history cause API 400 errors.
        # With the fix applied, API error count should be 0.
        if api_error_count > 0:
            print(
                "FAIL: Found API 400 errors from empty assistant messages in history."
            )
            print("The retry logic should not include empty assistant messages.")
            sys.exit(1)

        # Harness should have exhausted retries (non-interactive termination)
        if "LLM Move failed repeatedly" not in stdout_output:
            print("FAIL: Expected harness to exhaust retries.")
            sys.exit(1)

        # Read verbose log and verify:
        # 1. No empty assistant messages (never added — reset on empty)
        # 2. All attempts see exactly 1 message (the clean prompt)
        with open(verbose_file, "r") as f:
            lines = f.readlines()
            for i, line in enumerate(lines):
                rec = json.loads(line)
                api_req = rec.get("api_request", {})
                messages = api_req.get("messages", [])

                if len(messages) != 1:
                    print(
                        f"FAIL: Expected 1 message on attempt {i + 1}, "
                        f"got {len(messages)}."
                    )
                    sys.exit(1)

                for j, msg in enumerate(messages):
                    if (
                        msg.get("role") == "assistant"
                        and not msg.get("content", "").strip()
                    ):
                        print(
                            f"FAIL: Empty assistant found in verbose log "
                            f"entry {i}, index {j}."
                        )
                        sys.exit(1)

    print("PASS: Empty response with API rejection test successful.")
    print("  - No API 400 errors from empty assistant messages.")
    print("  - No empty assistant messages in API request history.")
    print("  - Harness exhausted retries cleanly.")


if __name__ == "__main__":
    test_empty_response_with_api_rejection()
