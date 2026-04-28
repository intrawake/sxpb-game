import json
import urllib.request
import urllib.error
import socket
import time
import sys
import argparse
import re

# API_URL removed


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
    timeout=0,
    log_file=None,
    reasoning_effort=None,
    return_full=False,
    api_url=None,
    **kwargs,
):
    # Map 0 or negative timeout to None (wait forever)
    if timeout is not None and timeout <= 0:
        timeout = None

    if isinstance(prompt, list):
        messages = prompt
    else:
        messages = [{"role": "user", "content": prompt}]

    payload = {
        "model": model,
        "messages": messages,
    }
    payload.update(kwargs)

    if reasoning_effort:
        payload["reasoning_effort"] = reasoning_effort
        if reasoning_effort == "none":
            payload.pop("reasoning_effort")
            payload["chat_template_kwargs"] = {"enable_thinking": False}

    # Simple hack: if model string implies local reasoning model, we might want to strip reasoning tokens or specific params
    # But standard OpenAI API doesn't have a universal "disable reasoning" flag yet.
    # For now, let's just leave it standard or add provider-specific hacks if we know the backend.

    def log_to_file(text):
        if not log_file:
            return
        try:
            with open(log_file, "a") as f:
                f.write(text + "\n")
        except Exception as e:
            sys.stderr.write(f"Logging Error: {e}\n")

    if log_file:
        log_to_file(f"\n--- API Request ---\n{json.dumps(payload, indent=2)}")

    data = json.dumps(payload).encode("utf-8")
    if not api_url:
        raise ValueError("api_url must be provided to call_api")

    target_url = api_url
    if not target_url.endswith("/chat/completions"):
        if not target_url.endswith("/"):
            target_url += "/"
        target_url += "chat/completions"

    req = urllib.request.Request(
        target_url, data=data, headers={"Content-Type": "application/json"}
    )

    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                res_data = json.loads(response.read().decode("utf-8"))
                choice = res_data["choices"][0]
                content = choice["message"].get("content") or ""
                content = content.strip()

                if log_file:
                    log_to_file(f"\n--- API Response ---\n{content}")
                if return_full:
                    return content, payload, res_data
                return content
        except urllib.error.HTTPError as e:
            err_body = ""
            try:
                err_body = e.read().decode("utf-8")
            except Exception:
                pass

            if (
                e.code == 429
                or "too many requests" in err_body.lower()
                or "rate limit" in err_body.lower()
            ):
                if attempt == 4:
                    sys.stderr.write("Rate limited on final attempt. Giving up.\n")
                    break
                sleep_time = 32 if attempt < 2 else 64
                sys.stdout.write(
                    f"Rate limited (429/Too Many Requests) on attempt {attempt + 1}. Retrying in {sleep_time}s...\n"
                )
                sys.stdout.flush()
                if log_file:
                    log_to_file(f"Rate limited: {err_body}")
                time.sleep(sleep_time)
            elif (
                e.code in [500, 502, 503, 504]
                or "timeout" in str(e).lower()
                or "timeout" in err_body.lower()
            ):
                sys.stdout.write(
                    f"Server Error/Timeout ({e.code}) on attempt {attempt + 1}. Retrying...\n"
                )
                sys.stdout.flush()
                if log_file:
                    log_to_file(f"Server Error ({e.code}): {err_body}")
                time.sleep(2)
            else:
                sys.stderr.write(
                    f"API Error ({e.code}): {e.reason}\nBody: {err_body}\n"
                )
                break
        except urllib.error.URLError as e:
            if isinstance(e.reason, socket.timeout) or "timeout" in str(e).lower():
                sys.stdout.write(f"URL Timeout on attempt {attempt + 1}. Retrying...\n")
                sys.stdout.flush()
                if log_file:
                    log_to_file(f"URL Timeout on attempt {attempt + 1}. Retrying...")
                time.sleep(2)
            else:
                sys.stderr.write(f"URL Error: {e}\n")
                break
        except TimeoutError:
            sys.stdout.write(f"Timeout Error on attempt {attempt + 1}. Retrying...\n")
            sys.stdout.flush()
            if log_file:
                log_to_file(f"Timeout Error on attempt {attempt + 1}. Retrying...")
            time.sleep(2)
        except Exception as e:
            sys.stderr.write(f"Request Error: {e}\n")
            break
    if return_full:
        return None, payload, None
    return None


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
    import sxpb

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

    return f"""\
You are a playing agent. You are player: {curr_player_id}
Your goal is to win the game or force a draw.{rules_section}{persona_section}{player_info_section}
### Current Game State (SxPB format)
```sxpb
{state_sxpb}
```

### Instructions
- Analyze the board and the move history.
- **Valid indices/moves:** {valid_str}
- Provide your next move using the following EXACT markdown format:
  ```sxpb >/dev/stdout
  (answer "your_move")
  ```
  - The string inside the quotes cannot contain newlines.
  - Keep the answer less than a paragraph if it's even allowed to be that long.

### Question
{prompt_q}"""
