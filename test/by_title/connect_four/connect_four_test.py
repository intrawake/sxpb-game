import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))

from sxpb_game.by_title.connect_four.logic import ConnectFourLogic


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def fresh():
    return ConnectFourLogic()


def assert_parse(g, move_str, expected):
    result = g.parse_move(move_str)
    assert result == expected, (
        f"parse_move({move_str!r}) => {result!r}, expected {expected!r} (heights={g.heights})"
    )


def assert_make(g, player_idx, move_str, should_succeed):
    before = list(g.heights)
    res = g.make_move(player_idx, move_str)
    assert res.success is should_succeed, (
        f"make_move({move_str!r}) success={res.success}, expected {should_succeed}"
    )
    if not should_succeed:
        assert g.heights == before, "heights must not change on rejected move"


# ---------------------------------------------------------------------------
# bare column: always accepted if column not full, regardless of height
# ---------------------------------------------------------------------------


def test_bare_column_accepted():
    g = fresh()
    # empty board — every column bare is valid
    for col in "abcdefg":
        assert_parse(g, col, "abcdefg".index(col))
        assert_parse(g, col.upper(), "abcdefg".index(col))

    # with surrounding whitespace (strip)
    assert_parse(g, " c ", 2)
    assert_parse(g, "  G  ", 6)

    # after stacking in c, bare c still means “next open row”
    g.make_move(0, "c")  # c1
    assert_parse(g, "c", 2)
    g.make_move(1, "c")  # c2
    assert_parse(g, "c", 2)
    g.make_move(0, "c")  # c3
    assert_parse(g, "c", 2)


# ---------------------------------------------------------------------------
# row-qualified: must equal heights[col]+1 (gravity) — the core bug was
# allowing "c2" when c1 empty, and ignoring row entirely before.
# ---------------------------------------------------------------------------


def test_row_must_match_gravity():
    g = fresh()

    # empty column c expects row 1
    assert_parse(g, "c1", 2)
    assert_parse(g, "c2", None)  # <-- the reported bug: c2 with empty c1
    assert_parse(g, "c3", None)
    assert_parse(g, "c6", None)
    assert_parse(g, "a2", None)
    assert_parse(g, "g2", None)

    # after one disc in c, expectation shifts to 2
    g.make_move(0, "c")  # c1
    assert_parse(g, "c1", None)  # too low — already occupied
    assert_parse(g, "c2", 2)  # next open
    assert_parse(g, "c3", None)  # too high — would leave gap
    assert_parse(g, "a1", 0)  # other columns still expect 1
    assert_parse(g, "a2", None)

    # after two discs in c, expectation is 3
    g.make_move(1, "c")  # c2
    assert_parse(g, "c3", 2)
    assert_parse(g, "c2", None)
    assert_parse(g, "c1", None)
    assert_parse(g, "c4", None)

    # bare still works at any height
    assert_parse(g, "c", 2)


def test_row_qualified_with_prefix():
    g = fresh()
    # optional R/Y prefix (case-insensitive, optional space)
    assert_parse(g, "Rc1", 2)
    assert_parse(g, "Yc1", 2)
    assert_parse(g, "R c1", 2)
    assert_parse(g, "Y c1", 2)
    assert_parse(g, "rC1", 2)
    assert_parse(g, "y c1", 2)
    assert_parse(g, "Y  c1", 2)

    # prefix does NOT change gravity check — c2 still wrong when empty
    assert_parse(g, "Rc2", None)
    assert_parse(g, "Yc2", None)

    # after c1 occupied, prefix-qualified next row is 2
    g.make_move(0, "c")
    assert_parse(g, "Rc2", 2)
    assert_parse(g, "Y c2", 2)
    assert_parse(g, "Rc1", None)


# ---------------------------------------------------------------------------
# strict full-string validation — must reject embedded/trailing/leading
# garbage. The previous re.search found a column *anywhere* inside the
# string, so "Ic2", "foo c1", "c1 extra" all slipped through.
# ---------------------------------------------------------------------------


def test_strict_rejects_garbage():
    g = fresh()

    garbage = [
        "Ic2",  # leading char before column (search would find c2)
        "Xc1",  # invalid prefix
        "Qc1",  # invalid prefix
        "foo c1",  # words before move
        "my move is c1",
        " c1 extra",  # trailing words (not just whitespace)
        "c1 extra",
        "Rc1 extra",
        "c1.",  # punctuation
        "c1,",
        "c1;",
        "c1,c2",  # comma-separated
        "a1b2",  # two moves jammed together
        "Ac1",  # extra letter before column
        "cc1",
        "c1c2",
        " b1 extra word",
        "Y c1 hello",
        "R c1!",
        "(c1)",
        "[c1]",
        "c 1",  # space inside coordinate
        "c-1",
        "c01",  # leading zero
    ]
    for s in garbage:
        assert_parse(g, s, None)

    # even after board has discs, garbage still rejected
    g.make_move(0, "c")  # c1
    assert_parse(g, "c2 extra", None)
    assert_parse(g, "Xc2", None)
    assert_parse(g, "foo c2", None)
    assert_parse(g, "c2.", None)


def test_strict_rejects_invalid_columns_and_rows():
    g = fresh()
    invalid = [
        "",
        " ",
        "   ",  # empty / whitespace
        "h1",
        "z1",
        "1c",  # column out of range
        "a0",
        "a7",
        "a8",
        "c0",  # row out of 1-6
        "a-1",
        "a10",
        "-",
        "R",
        "Y",  # prefix alone
        "RYa1",
        "RRc1",
    ]
    for s in invalid:
        assert_parse(g, s, None)

    # None / empty handling
    assert g.parse_move("") is None
    assert g.parse_move("   ") is None
    assert g.parse_move(None) is None


def test_full_column_rejects_all():
    g = fresh()
    for i in range(6):
        assert g.make_move(i % 2, "a").success
    # column a is full — bare and any row must fail
    assert_parse(g, "a", None)
    assert_parse(g, "a1", None)
    assert_parse(g, "a6", None)
    assert_parse(g, "a7", None)
    assert_parse(g, "Ra1", None)
    # other columns unaffected
    assert_parse(g, "b", 1)
    assert_parse(g, "b1", 1)
    assert_parse(g, "b2", None)


# ---------------------------------------------------------------------------
# make_move integration — row-qualified moves through the game API
# ---------------------------------------------------------------------------


def test_make_move_row_qualified():
    g = fresh()
    assert_make(g, 0, "c1", True)
    assert g.heights[2] == 1
    assert g.history == ["Rc1"]

    assert_make(g, 1, "c2", True)
    assert g.heights[2] == 2
    assert g.history[-1] == "Yc2"

    # mismatched gravity via make_move must also fail
    assert_make(g, 0, "c1", False)
    assert_make(g, 0, "c4", False)
    assert_make(g, 0, "c2", False)  # expects c3 now
    assert_make(g, 0, "Ic2", False)  # garbage
    assert_make(g, 0, "c3 extra", False)

    # bare still works
    assert_make(g, 0, "c", True)
    assert g.heights[2] == 3
    assert g.history[-1] == "Rc3"

    # wrong player turn also rejected (even if move string valid)
    # now it's Y's turn, R trying to move should fail
    assert g.get_current_player() == 1
    assert_make(g, 0, "d", False)
    assert_make(g, 1, "d1", True)


def test_make_move_does_not_mutate_on_invalid():
    g = fresh()
    g.make_move(0, "c")  # c1
    heights_before = list(g.heights)
    assert not g.make_move(1, "c1").success  # expects c2
    assert g.heights == heights_before
    assert not g.make_move(1, "foo c2").success
    assert g.heights == heights_before


# ---------------------------------------------------------------------------
# regression: the exact bug report — "c2" when nothing in "c1"
# parametrised over every column
# ---------------------------------------------------------------------------


def test_all_columns_c2_when_empty():
    for col in "abcdefg":
        g = fresh()
        idx = "abcdefg".index(col)
        assert g.parse_move(f"{col}2") is None, (
            f"{col}2 should be rejected on empty board"
        )
        assert g.parse_move(f"{col}1") == idx, (
            f"{col}1 should be accepted on empty board"
        )
        assert not g.make_move(0, f"{col}2").success
        assert g.make_move(0, f"{col}1").success or g.make_move(0, col).success
