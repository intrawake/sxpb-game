import sxpb


def parse_move(content):
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


def test_parse_move():
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
        assert parse_move(content) == expected
