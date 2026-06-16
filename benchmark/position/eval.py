import sys
import os
import argparse
import json
import re

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", "src"))
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

from sxpb_game.eval.utils import call_api, generate_prompt
import sxpb
from sxpb_game.by_title.tictactoe.logic import TicTacToeLogic


def get_base_game():
    game = TicTacToeLogic()
    # Moves for Base Case (Immediate Win at a3)
    # Xb2 Oa1 Xc2 Oa2 Xb1 -> O wins at a3
    game.make_move(0, "b2")
    game.make_move(1, "a1")
    game.make_move(0, "c2")
    game.make_move(1, "a2")
    game.make_move(0, "b1")
    return game


def get_hunter_blunder_game():
    """
    Reconstructs the state from the match where Hunter Alpha blundered.
    Moves: Xb2 Oa1 Xc3 Oa3 Xa2 Oc2 Xb1
    Valid moves: b3, c1
    Correct move is b3 (to block row 2/column b).
    """
    game = TicTacToeLogic()
    game.make_move(0, "b2")
    game.make_move(1, "a1")
    game.make_move(0, "c3")
    game.make_move(1, "a3")
    game.make_move(0, "a2")
    game.make_move(1, "c2")
    game.make_move(0, "b1")
    return game


def generate_scenario_r0c0(game_fn):
    game = game_fn()
    prompt = generate_prompt(game, 1)  # Player O
    # For hunter blunder: expected is b3 (to block column b)
    if game_fn == get_hunter_blunder_game:
        return prompt, ["b3"]
    return prompt, ["a3"]  # Default for base game


def to_alphanumeric(prompt: str) -> str:
    # Logic is already alphanumeric.
    return prompt


def to_bracket(prompt: str) -> str:
    def replacer(match):
        col = {"a": 0, "b": 1, "c": 2}[match.group(1)]
        row = {"1": 0, "2": 1, "3": 2}[match.group(2)]
        return f"[{row}][{col}]"

    p = re.sub(r"\b([abc])([123])\b", replacer, prompt)

    def prefix_replacer(match):
        col = {"a": 0, "b": 1, "c": 2}[match.group(2)]
        row = {"1": 0, "2": 1, "3": 2}[match.group(3)]
        return f"{match.group(1)}[{row}][{col}]"

    p = re.sub(r"\b([XO])([abc])([123])\b", prefix_replacer, p)
    return p


def to_at(prompt: str) -> str:
    p = prompt.replace("Columns: a b c", "Columns: 0 1 2")

    def replacer(match):
        col = {"a": 0, "b": 1, "c": 2}[match.group(1)]
        row = {"1": 0, "2": 1, "3": 2}[match.group(2)]
        return f"@{row},{col}"

    p = re.sub(r"\b([abc])([123])\b", replacer, p)

    def prefix_replacer(match):
        col = {"a": 0, "b": 1, "c": 2}[match.group(2)]
        row = {"1": 0, "2": 1, "3": 2}[match.group(3)]
        return f"{match.group(1)}@{row},{col}"

    p = re.sub(r"\b([XO])([abc])([123])\b", prefix_replacer, p)
    return p


def to_at_bracket(prompt: str) -> str:
    p = prompt.replace("Columns: a b c", "Columns: 0 1 2")

    def replacer(match):
        col = {"a": 0, "b": 1, "c": 2}[match.group(1)]
        row = {"1": 0, "2": 1, "3": 2}[match.group(2)]
        return f"@[{row},{col}]"

    p = re.sub(r"\b([abc])([123])\b", replacer, p)

    p = (
        p.replace("(row3 (())", "(row2 (())")
        .replace("(row2 (())", "(row1 (())")
        .replace("(row1 (())", "(row0 (())")
    )

    def prefix_replacer(match):
        col = {"a": 0, "b": 1, "c": 2}[match.group(2)]
        row = {"1": 0, "2": 1, "3": 2}[match.group(3)]
        return f"{match.group(1)}@[{row},{col}]"

    p = re.sub(r"\b([XO])([abc])([123])\b", prefix_replacer, p)
    return p


def to_at_r0c0(prompt: str) -> str:
    def replacer(match):
        col = {"a": 0, "b": 1, "c": 2}[match.group(1)]
        row = {"1": 0, "2": 1, "3": 2}[match.group(2)]
        return f"@r{row}c{col}"

    p = re.sub(r"\b([abc])([123])\b", replacer, prompt)

    def prefix_replacer(match):
        col = {"a": 0, "b": 1, "c": 2}[match.group(2)]
        row = {"1": 0, "2": 1, "3": 2}[match.group(3)]
        return f"{match.group(1)}@r{row}c{col}"

    p = re.sub(r"\b([XO])([abc])([123])\b", prefix_replacer, p)
    return p


def to_markdown_table(prompt: str) -> str:
    # Extracts board from SxPB and converts to Markdown
    # (row0 (()) O _ X)
    # (row1 (()) X X O)
    # (row2 (()) O X _)
    rows = []
    for r in range(3):
        match = re.search(
            r"\(row" + str(r) + r" \(\(\)\) ([_XO]) ([_XO]) ([_XO])\)", prompt
        )
        if match:
            rows.append(f"| {r} | " + " | ".join(match.groups()) + " |")
        else:
            # Try r0 format
            match = re.search(
                r"\(r" + str(r) + r" \(\(\)\) ([_XO]) ([_XO]) ([_XO])\)", prompt
            )
            if match:
                rows.append(f"| {r} | " + " | ".join(match.groups()) + " |")

    table = "| | 0 | 1 | 2 |\n|---|---|---|---|\n" + "\n".join(rows)

    # Replace the board section
    p = re.sub(
        r"```sxpb\n.*?\n```", f"```markdown\n{table}\n```", prompt, flags=re.DOTALL
    )
    return p


def to_markdown_table_a1(prompt: str) -> str:
    # Extracts board from SxPB and converts to Markdown with a1 labels
    # row3 (()) _ _ _
    # row2 (()) O X X
    # row1 (()) O X _
    rows = []
    # Alphanumeric board usually has rows 3, 2, 1
    for r in [3, 2, 1]:
        match = re.search(
            r"\(row" + str(r) + r" \(\(\)\) ([_XO]) ([_XO]) ([_XO])\)", prompt
        )
        if match:
            rows.append(f"| {r} | " + " | ".join(match.groups()) + " |")

    table = "| | a | b | c |\n|---|---|---|---|\n" + "\n".join(rows)

    # Replace the board section
    p = re.sub(
        r"```sxpb\n.*?\n```", f"```markdown\n{table}\n```", prompt, flags=re.DOTALL
    )
    return p


def main():
    parser = argparse.ArgumentParser(description="Coordinate Benchmark Evaluator")
    parser.add_argument(
        "--model",
        default="dono-gemini-lite",
        help="Model to evaluate (e.g. dono-gemini-lite)",
    )
    parser.add_argument(
        "--model_by_name",
        default=os.path.join(
            os.path.dirname(__file__), "..", "..", "preset", "model_by_name.sxpb"
        ),
        help="SxPB string or file defining model-specific overrides",
    )
    parser.add_argument(
        "--dump_prompts",
        default="",
        help="Filepath to write the prompts to as JSONL (default: empty string to run live evaluation)",
    )
    parser.add_argument(
        "--openai_api_url",
        dest="openai_api_url",
        required=True,
        help="OpenAI-compatible API URL (e.g. https://api.openai.com/v1)",
    )
    args = parser.parse_args()

    # Load model overrides
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

    requested_model = args.model
    api_kwargs = {}
    model = requested_model

    if requested_model in model_overrides:
        m_over = model_overrides[requested_model]
        if isinstance(m_over, str):
            model = m_over
        elif isinstance(m_over, dict):
            api_kwargs = dict(m_over)
            if "fullname" in api_kwargs:
                model = api_kwargs.pop("fullname")

    if "temperature" in api_kwargs:
        api_kwargs["temperature"] = float(api_kwargs["temperature"])

    print(f"Evaluating model: {model} (requested: {requested_model})")
    sys.stdout.flush()

    results = {}

    scenarios = [
        ("Base Case (Immediate Win)", get_base_game, "a3"),
        ("Hunter Blunder (Block Column B)", get_hunter_blunder_game, "b3"),
    ]

    for sc_name, sc_fn, sc_exp in scenarios:
        print(f"\n=== Scenario: {sc_name} ===")
        sys.stdout.flush()
        # Need the game object to check valid moves
        game = sc_fn()
        r0c0_prompt, _ = generate_scenario_r0c0(sc_fn)

        # Valid moves in internal format (a1, b2, etc.)
        valid_moves_internal = game.get_valid_moves()

        # Expected coordinate in a1
        exp_a1 = sc_exp

        # Map a1 to internal row/col
        col_map = {"a": 0, "b": 1, "c": 2}
        row_map = {"1": 0, "2": 1, "3": 2}
        exp_c = col_map[exp_a1[0]]
        exp_r = row_map[exp_a1[1]]

        prompts = {
            f"{sc_name} [a1]": {
                "prompt": r0c0_prompt,
                "expected": exp_a1,
                "format": "a1",
            },
            f"{sc_name} [bracket]": {
                "prompt": to_bracket(r0c0_prompt),
                "expected": f"[{exp_r}][{exp_c}]",
                "format": "bracket",
            },
            f"{sc_name} [at]": {
                "prompt": to_at(r0c0_prompt),
                "expected": f"@{exp_r},{exp_c}",
                "format": "at",
            },
            f"{sc_name} [at_bracket]": {
                "prompt": to_at_bracket(r0c0_prompt),
                "expected": f"@[{exp_r},{exp_c}]",
                "format": "at_bracket",
            },
            f"{sc_name} [at_r0c0]": {
                "prompt": to_at_r0c0(r0c0_prompt),
                "expected": f"@r{exp_r}c{exp_c}",
                "format": "at_r0c0",
            },
            f"{sc_name} [md_table]": {
                "prompt": to_markdown_table(r0c0_prompt),
                "expected": exp_a1,
                "format": "a1",
            },
            f"{sc_name} [md_table_a1]": {
                "prompt": to_markdown_table_a1(r0c0_prompt),
                "expected": exp_a1,
                "format": "a1",
            },
        }

        if args.dump_prompts:
            with open(args.dump_prompts, "a") as f:
                for name, p in prompts.items():
                    f.write(
                        json.dumps(
                            {
                                "scenario": name,
                                "prompt": p["prompt"],
                                "expected": [p["expected"]],
                            }
                        )
                        + "\n"
                    )
            continue

        for name, p in prompts.items():
            print(f"\n--- Testing Format: {name} ---")
            sys.stdout.flush()
            try:
                content, _, _ = call_api(
                    model,
                    p["prompt"],
                    return_full=True,
                    api_url=args.openai_api_url,
                    **api_kwargs,
                )
            except Exception as e:
                print(f"API call failed: {e}")
                content = ""

            if not content:
                print("Received empty response.")
                results[name] = {
                    "answer": None,
                    "status": "INVALID",
                    "expected": p["expected"],
                }
                continue

            # parse the answer
            answer = None
            for line in reversed(content.strip().splitlines()):
                line = line.strip("` \t;")
                if line.startswith("(answer ") and line.endswith(")"):
                    inner = line[8:-1].strip()
                    if (
                        len(inner) >= 2
                        and inner.startswith('"')
                        and inner.endswith('"')
                    ):
                        answer = inner[1:-1]
                    else:
                        answer = inner

                    # Strip leading O or X prefix if present (e.g. Oa1 -> a1)
                    if (
                        answer
                        and len(answer) > 1
                        and answer[0].upper() in ["X", "O"]
                        and answer[1].lower() in ["a", "b", "c", "r", "[", "@"]
                    ):
                        answer = answer[1:]
                    break

            # Determine status: PASS, FAIL (valid but wrong), INVALID (parsing error or illegal move)
            status = "INVALID"
            if answer:
                if answer == p["expected"]:
                    status = "PASS"
                else:
                    # Check if answer is a valid move in the requested format
                    is_valid_move = False
                    if p["format"] == "a1":
                        # answer should be a1, b2, etc
                        is_valid_move = answer in valid_moves_internal
                    elif p["format"] == "bracket":
                        try:
                            # [r][c]
                            r = int(answer[1])
                            c = int(answer[4])
                            internal_move = game.format_move(c, r)
                            is_valid_move = internal_move in valid_moves_internal
                        except Exception:
                            pass
                    elif p["format"] == "at":
                        try:
                            # @r,c
                            r = int(answer[1])
                            c = int(answer[3])
                            internal_move = game.format_move(c, r)
                            is_valid_move = internal_move in valid_moves_internal
                        except Exception:
                            pass
                    elif p["format"] == "at_bracket":
                        try:
                            # @[r,c]
                            r = int(answer[2])
                            c = int(answer[4])
                            internal_move = game.format_move(c, r)
                            is_valid_move = internal_move in valid_moves_internal
                        except Exception:
                            pass
                    elif p["format"] == "at_r0c0":
                        try:
                            # @r0c0
                            r = int(answer[2])
                            c = int(answer[4])
                            internal_move = game.format_move(c, r)
                            is_valid_move = internal_move in valid_moves_internal
                        except Exception:
                            pass

                    if is_valid_move:
                        status = "FAIL"
                    else:
                        status = "INVALID"

            print(f"Extracted Answer: {answer}")
            print(f"Status: {status}")
            results[name] = {
                "answer": answer,
                "status": status,
                "expected": p["expected"],
            }

    if not args.dump_prompts:
        print("\n--- Summary ---")
        for k, v in results.items():
            st = v["status"]
            assert st is not None
            status_icon = {"PASS": "✅", "FAIL": "❌", "INVALID": "🚫"}[st]
            print(
                f"{k}: {status_icon} {v['status']} (got {v['answer']}, expected {v['expected']})"
            )


if __name__ == "__main__":
    if os.path.exists("eval_prompts.jsonl") and "--dump_prompts" in sys.argv:
        os.remove("eval_prompts.jsonl")
    main()
