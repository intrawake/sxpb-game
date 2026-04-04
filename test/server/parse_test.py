import sxpb


def parse_move(content):
    move = None
    for line in reversed(content.strip().splitlines()):
        line = line.strip("` \t;")
        if (
            line.startswith("(answer ") or line.startswith('(answer"')
        ) and line.endswith(")"):
            try:
                parsed = sxpb.loads(line)
                if isinstance(parsed, dict) and "answer" in parsed:
                    move = parsed["answer"]
                    break
            except Exception:
                # Fallback if sxpb parsing fails for some reason
                if line.startswith("(answer "):
                    inner = line[8:-1].strip()
                else:
                    inner = line[7:-1].strip()
                if len(inner) >= 2 and inner.startswith('"') and inner.endswith('"'):
                    move = inner[1:-1]
                else:
                    move = inner
                break
    return move


def test_parse_move():
    tests = [
        ('(answer "p1 0!")', "p1 0!"),
        ('(answer"p1 0!")', "p1 0!"),
        ('Here is my move:\n```sxpb\n`(answer "p2? hi there")`\n```', "p2? hi there"),
        ("```(answer p3!)```", "p3!"),
        ('`(answer "??? who are you")`', "??? who are you"),
        (
            '`(answer "??? Alright everyone, new round! Let’s share some info—how many Elder Signs or Blanks do you *claim* to have in your hand this round? (Remember, Cultists might be lying!)");`',
            "??? Alright everyone, new round! Let’s share some info—how many Elder Signs or Blanks do you *claim* to have in your hand this round? (Remember, Cultists might be lying!)",
        ),
    ]

    for content, expected in tests:
        assert parse_move(content) == expected
