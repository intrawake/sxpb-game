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


def parse_strict_move(content):
    import re

    matches = list(
        re.finditer(
            r"(?:^|\n)[ \t]*```[ \t]*sxpb[ \t]*>[ \t]*/dev/stdout[ \t]*\r?\n(.*?)\r?\n[ \t]*```[ \t]*(?:\r?\n|$)",
            content,
            re.DOTALL,
        )
    )
    if matches:
        block_content = matches[-1].group(1)
        try:
            parsed_block = sxpb.loads(block_content)
            if isinstance(parsed_block, dict) and "answer" in parsed_block:
                return parsed_block["answer"]
        except Exception:
            pass
    return None


def test_parse_strict_move():
    tests = [
        ('```sxpb >/dev/stdout\n(answer "p1 0!")\n```', "p1 0!"),
        ('some text\n```sxpb >/dev/stdout\n(answer "p2")\n```\nmore text', "p2"),
        ('```sxpb >/dev/stdout\n(answer "p3")\n(other "data")\n```', "p3"),
        ('```sxpb\n >/dev/stdout\n(answer "p4")\n```', None),
        ('```\nsxpb > /dev/stdout\n(answer "p5")\n```', None),
        ('```sxpb > /dev/stdout\n(answer "p6")\n```', "p6"),
        (' ```sxpb >/dev/stdout  \n(answer "p7")\n  ```  ', "p7"),
        ('```sxpb >/dev/stdout (answer "p8")\n```', None),
        ('```sxpb >/dev/stdout\n(answer "p9") ```', None),
        ('```sxpb >/dev/stdout\n(answer "p10")\n``` ', "p10"),
    ]
    for content, expected in tests:
        assert parse_strict_move(content) == expected
