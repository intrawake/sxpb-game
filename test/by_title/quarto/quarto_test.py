import copy
import random
import subprocess
import sys
from itertools import combinations
from pathlib import Path
from string import ascii_letters

import pytest
import sxpb
from sxpb_llm import parse_sxpb_answer

from sxpb_game.by_title.quarto.logic import (
    ATTRIBUTE_VALUES,
    LETTERS,
    LINES,
    SQUARES,
    QuartoLogic,
)
from sxpb_game.eval.logic import Outcome
from sxpb_game.eval.utils import generate_prompt


# Pieces in square order: a1–d1, a2–d2, a3–d3, a4–d4.
DRAW_BOARD = "p d i I U a T O t u D H A P o h".split()
FINAL_WIN_BOARD = "P D o I t i A U p T h u a d H O".split()


def play(game, move):
    player = game.get_current_player()
    assert player is not None
    result = game.make_move(player, move)
    assert result.success, result.reason


def assert_rejected(game, player, move):
    before = copy.deepcopy(game.__dict__)
    result = game.make_move(player, move)
    assert not result.success
    assert result.reason
    assert game.__dict__ == before


def play_board(pieces):
    game = QuartoLogic()
    play(game, f"give {pieces[0]}")
    for index, square in enumerate(SQUARES):
        gift = f" give {pieces[index + 1]}" if index < 15 else ""
        play(game, f"place {square}{gift}")
    return game


def piece_attributes(piece):
    letter = LETTERS[piece]
    base = letter.lower()
    return (
        "upper" if letter.isupper() else "lower",
        "vowel" if base in "aiou" else "consonant",
        "hole" if base in "adop" else "no-hole",
        "first-half" if base <= "m" else "last-half",
    )


def oracle_has_win(board):
    # Independent geometry and letter properties, not the engine's bit tests.
    rows = [[f"{col}{row}" for col in "abcd"] for row in range(1, 5)]
    cols = [[f"{col}{row}" for row in range(1, 5)] for col in "abcd"]
    diagonals = [["a1", "b2", "c3", "d4"], ["a4", "b3", "c2", "d1"]]
    for line in rows + cols + diagonals:
        pieces = [board[pos] for pos in line]
        if any(piece is None for piece in pieces):
            continue
        descriptions = [
            piece_attributes(piece) for piece in pieces if piece is not None
        ]
        if any(
            len({description[index] for description in descriptions}) == 1
            for index in range(4)
        ):
            return True
    return False


def test_initial_state():
    game = QuartoLogic()
    assert game.get_player_identifiers() == ["p1", "p2"]
    assert game.get_outcome_player_indices() == [0, 1]
    assert game.get_visible_players(0) == []
    assert game.get_current_player() == 0
    assert not game.is_game_over()
    assert game.get_player_outcomes() == {}
    assert game.available_pieces == list(range(16))
    with pytest.raises(ValueError, match="exactly two"):
        QuartoLogic(num_players=3)


def test_offer_is_reserved_and_placement_uses_it():
    game = QuartoLogic()
    play(game, "  GIVE A  ")
    assert game.get_current_player() == 1
    assert game.offered_piece == LETTERS.index("A")
    assert LETTERS.index("A") not in game.available_pieces
    assert all(piece is None for piece in game.board.values())
    play(game, "PLACE B2 GiVe p")
    assert game.board["b2"] == LETTERS.index("A")
    assert game.offered_piece == 0
    assert 0 not in game.available_pieces
    assert game.get_current_player() == 0
    assert game.move_count == 2
    assert game.history[-1] == sxpb.Lone(p2="place b2 give p")
    view = sxpb.loads(game.render_player_view(0))
    assert isinstance(view, dict)
    assert view["offered_piece"] == "p"
    assert "Place p" in game.get_prompt(0)


@pytest.mark.parametrize(
    "move", ["", "place a1 give A", "give", "give nope", "give A extra", "A"]
)
def test_invalid_opening_is_atomic(move):
    assert_rejected(QuartoLogic(), 0, move)


def test_index_bits_match_letter_attributes():
    assert LETTERS == "potudahiPOTUDAHI"
    for piece, letter in enumerate(LETTERS):
        base = letter.lower()
        expected = (
            base in "aiou",
            base in "hitu",
            base <= "m",
            letter.isupper(),
        )
        assert tuple(bool(piece & (1 << bit)) for bit in range(4)) == expected
    view = sxpb.loads(QuartoLogic().render_player_view(0))
    assert isinstance(view, dict)
    assert view["available_pieces"] == list(LETTERS)


@pytest.mark.parametrize("piece,letter", list(enumerate(LETTERS)))
def test_every_letter_can_be_given_and_preserves_case_through_the_llm_parser(
    piece, letter
):
    move = f"give {letter}"
    assert parse_sxpb_answer(f'```sxpb > /dev/stdout\n(answer "{move}")\n```') == move
    game = QuartoLogic()
    play(game, move)
    assert game.offered_piece == piece
    assert piece not in game.available_pieces
    view = sxpb.loads(game.render_player_view(0))
    assert isinstance(view, dict)
    assert view["offered_piece"] == letter
    assert letter not in view["available_pieces"]
    assert game.history[0] == sxpb.Lone(p1=move)
    assert letter in game.get_prompt(1)


@pytest.mark.parametrize("lower", list(LETTERS[:8]))
def test_piece_case_is_significant_but_commands_and_coordinates_are_not(lower):
    upper = lower.upper()
    lower_piece, upper_piece = LETTERS.index(lower), LETTERS.index(upper)
    game = QuartoLogic()
    play(game, f"GIVE {lower}")
    assert game.offered_piece == lower_piece
    assert upper_piece in game.available_pieces
    assert lower_piece not in game.available_pieces
    assert_rejected(game, 1, f"place a1 give {lower}")
    assert_rejected(game, 1, f"place a1 give {lower_piece}")
    play(game, f"PlAcE A1 GiVe {upper}")
    assert game.board["a1"] == lower_piece
    assert game.offered_piece == upper_piece
    assert game.history[-1] == sxpb.Lone(p2=f"place a1 give {upper}")


@pytest.mark.parametrize(
    "piece",
    [letter for letter in ascii_letters if letter not in LETTERS]
    + [
        "·",
        "_",
        "____",
        "↑",
        "↥",
        "⇧",
        "⇦",
        "⬆",
        "⬆︎",
        "⬆️",
        "⇐",
        "pp",
        "po",
        "POTU",
        "TLRH",
        "tlrh",
        "SDQS",
        "sdqs",
        "0",
        "15",
        "p!",
        "P\ufe0e",
        "ｐ",
        "р",
    ],
)
def test_other_letters_empty_markers_and_retired_arrows_are_not_pieces(piece):
    assert_rejected(QuartoLogic(), 0, f"give {piece}")


def test_wrong_player_is_atomic():
    game = QuartoLogic()
    assert_rejected(game, 1, "give A")
    assert_rejected(game, -1, "give A")
    play(game, "give A")
    assert_rejected(game, 0, "place a1 give O")


@pytest.mark.parametrize(
    "move",
    [
        "",
        "give O",
        "place a1",
        "place a1 give A",
        "place a1 give NOPE",
        "place e1 give O",
        "place a0 give O",
        "place a5 give O",
        "place a1 gift O",
        "place a1 give O extra",
        "place a1 O",
        "place a1 give O;",
        "place a01 give O",
        "place a1 give",
    ],
)
def test_invalid_compound_move_is_atomic(move):
    game = QuartoLogic()
    play(game, "give A")
    assert_rejected(game, 1, move)


def test_occupied_square_and_used_gift_are_rejected():
    game = QuartoLogic()
    play(game, "give A")
    play(game, "place a1 give O")
    assert_rejected(game, 0, "place a1 give t")
    assert_rejected(game, 0, "place b1 give A")


@pytest.mark.parametrize("line_name,line", LINES)
@pytest.mark.parametrize("attribute_index", range(4))
@pytest.mark.parametrize("value_index", range(2))
def test_every_line_and_both_values_of_every_attribute(
    line_name, line, attribute_index, value_index
):
    pieces = [
        piece
        for piece in range(len(LETTERS))
        if (piece >> attribute_index) & 1 == value_index
    ][:4]
    game = QuartoLogic()
    for square, piece in zip(line[:3], pieces[:3]):
        game.board[square] = piece
    game.offered_piece = pieces[3]
    game.available_pieces = [
        piece for piece in range(len(LETTERS)) if piece not in pieces
    ]
    game.move_count = 4
    play(game, f"place {line[3]}")
    assert game.winner == "p1"
    assert game.winning_line == line_name
    assert ATTRIBUTE_VALUES[attribute_index][value_index] in game.winning_attributes
    assert game.get_player_outcomes() == {0: Outcome.WIN, 1: Outcome.LOSS}
    assert game.get_current_player() is None


def test_all_four_piece_combinations_against_attribute_set_oracle():
    game = QuartoLogic()
    for pieces in combinations(range(len(LETTERS)), 4):
        for square, piece in zip(("a1", "b1", "c1"), pieces[:3]):
            game.board[square] = piece
        expected = set.intersection(*(set(piece_attributes(piece)) for piece in pieces))
        line, attributes = game._winning_alignment("d1", pieces[3])
        assert set(attributes) == expected
        assert line == ("row1" if expected else None)


def test_no_shared_attribute_and_no_small_square_win():
    for squares in [("a1", "b1", "c1", "d1"), ("a1", "b1", "a2", "b2")]:
        game = QuartoLogic()
        pieces = [
            LETTERS.index(letter)
            for letter in ("AUph" if squares[2] == "c1" else "AOIU")
        ]
        for square, piece in zip(squares[:3], pieces[:3]):
            game.board[square] = piece
        game.offered_piece = pieces[3]
        game.available_pieces = [
            piece for piece in range(len(LETTERS)) if piece not in pieces
        ]
        gift = game.available_pieces[0]
        play(game, f"place {squares[3]} give {LETTERS[gift]}")
        assert not game.is_game_over()


@pytest.mark.parametrize("extra_gift", ["", " give p"])
def test_reachable_win_is_automatic_and_terminal(extra_gift):
    game = QuartoLogic()
    for move in [
        "give A",
        "place a1 give P",
        "place b1 give U",
        "place c1 give H",
    ]:
        play(game, move)
    assert_rejected(game, 0, "place d1 give A")
    assert_rejected(game, 0, "place d1 give ⇐")
    play(game, "place d1" + extra_gift)
    assert game.winner == "p1"
    assert game.winning_attributes == ["upper"]
    assert game.offered_piece is None
    view = sxpb.loads(game.render_player_view(0))
    assert isinstance(view, dict)
    assert view["offered_piece"] == "_"
    assert 0 in game.available_pieces  # terminal gift is not reserved
    assert game.history[-1] == sxpb.Lone(p1=f"place d1{extra_gift}")
    assert_rejected(game, 1, "give d")
    assert game.get_algorithm_move(1, "random")[0] is None


def test_full_board_draw_in_seventeen_moves():
    game = play_board(DRAW_BOARD)
    assert not oracle_has_win(game.board)
    assert game.winner == "Draw"
    assert game.move_count == 17
    assert game.available_pieces == []
    assert game.offered_piece is None
    assert game.get_player_outcomes() == {0: Outcome.DRAW, 1: Outcome.DRAW}


def test_winning_final_placement_beats_draw():
    game = play_board(FINAL_WIN_BOARD)
    assert oracle_has_win(game.board)
    assert game.move_count == 17
    assert game.winner == "p1"
    assert game.get_player_outcomes() == {0: Outcome.WIN, 1: Outcome.LOSS}


def test_audit_snapshot_has_a_real_shared_attribute_threat():
    root = Path(__file__).resolve().parents[3]
    example = root / "example" / "view_by_title" / "quarto"
    players = sxpb.loads((example / "players.sxpb").read_text())
    assert isinstance(players, list)
    game = QuartoLogic()
    while not game.is_game_over():
        player = game.get_current_player()
        assert player is not None
        if not players[player]["premoves"]:
            break
        play(game, players[player]["premoves"].pop(0))
    assert game.render_player_view(0) == (example / "state.sxpb").read_text().strip()
    assert "(row1 (()) A P U _)" in game.render_player_view(0)
    assert game.offered_piece == LETTERS.index("H")
    assert game.get_current_player() == 1
    # p2 completes the line even though p1 placed one of its first three pieces.
    play(game, "place d1")
    assert game.winner == "p2"
    assert game.get_player_outcomes() == {0: Outcome.LOSS, 1: Outcome.WIN}
    assert game.winning_line == "row1"
    assert game.winning_attributes == ["upper"]


def test_history_is_a_chronological_manyof_of_player_moves():
    game = QuartoLogic()
    for move in ["give p", "place a1 give P", "place b2 give o"]:
        play(game, move)
    expected = [
        {"p1": "give p"},
        {"p2": "place a1 give P"},
        {"p1": "place b2 give o"},
    ]
    text = game.render_player_history(0)
    assert text == game.render_player_history(1)
    assert text == (
        "; --- Move History ---\n"
        "((history)\n"
        " (p1 give p)\n"
        " (p2 place a1 give P)\n"
        " (p1 place b2 give o)\n"
        ")"
    )
    decoded = sxpb.loads(text, precise=True)
    assert isinstance(decoded, sxpb.Mesg)
    assert isinstance(decoded["history"], sxpb.Many)
    assert all(isinstance(entry, sxpb.Lone) for entry in decoded["history"])
    assert decoded["history"].to_list() == expected
    roundtrip = sxpb.loads(sxpb.dumps(decoded), precise=True)
    assert isinstance(roundtrip, sxpb.Mesg)
    assert isinstance(roundtrip["history"], sxpb.Many)
    assert all(isinstance(entry, sxpb.Lone) for entry in roundtrip["history"])
    assert roundtrip["history"].to_list() == expected


def test_views_history_and_prompt_are_parseable_and_symmetric():
    game = QuartoLogic()
    play(game, "give A")
    play(game, "place b2 give t")
    view = sxpb.loads(game.render_player_view(0))
    assert isinstance(view, dict)
    assert view["board"]["row2"] == ["_", "A", "_", "_"]
    assert all(
        cell == "_" or cell in LETTERS for row in view["board"].values() for cell in row
    )
    assert all(len(cell) == 1 for row in view["board"].values() for cell in row)
    assert "piece_by_id" not in view
    assert view["offered_piece"] == "t"
    assert view["player_to_move"] == "p1"
    assert game.render_player_view(0) == game.render_player_view(1)
    history = sxpb.loads(game.render_player_history(0))
    assert isinstance(history, dict)
    assert history["history"] == game.history.to_list()
    assert "moves" not in history
    full_view = sxpb.loads(game.render_player_full_sxpb(0))
    assert isinstance(full_view, dict)
    assert full_view["offered_piece"] == "t"
    prompt = generate_prompt(game, 0)
    assert "place <square> give <piece>" in prompt
    assert "You are player: p1" in prompt
    rules = game.get_rules()
    assert rules.strip()
    assert f"### Rules\n{rules}\n" in prompt
    assert "piece_by_id" not in prompt
    # Do not reveal tactical hints by enumerating only winning bare placements.
    assert "Valid indices/moves: Any valid move" in prompt
    assert game.get_algorithm_move(0, "unsupported")[1]
    assert game.get_algorithm_move(1, "random")[1]


@pytest.mark.parametrize("seed", range(50))
def test_random_games_obey_independent_oracle_and_replay(seed, monkeypatch):
    rng = random.Random(seed)
    monkeypatch.setattr(random, "choice", rng.choice)
    game = QuartoLogic()
    while not game.is_game_over():
        assert game.move_count < 17
        player = game.get_current_player()
        assert player is not None
        move, error = game.get_algorithm_move(player, "random")
        assert error is None and move is not None
        play(game, move)
        placed = [piece for piece in game.board.values() if piece is not None]
        pending = [game.offered_piece] if game.offered_piece is not None else []
        inventory = placed + pending + game.available_pieces
        assert len(inventory) == len(set(inventory)) == 16
        assert set(inventory) == set(range(len(LETTERS)))
        if oracle_has_win(game.board):
            assert game.winner == game.get_player_identifiers()[player]
        elif len(placed) == 16:
            assert game.winner == "Draw"
        else:
            assert game.winner is None
        sxpb.loads(game.render_player_full_sxpb(0))
    # Replay the public manyof, not the in-memory representation.
    decoded = sxpb.loads(game.render_player_history(0), precise=True)
    assert isinstance(decoded, sxpb.Mesg)
    history = decoded["history"]
    assert isinstance(history, sxpb.Many)
    replay = QuartoLogic()
    for record in history:
        assert isinstance(record, sxpb.Lone) and len(record) == 1
        player_id, move = next(iter(record.items()))
        player = replay.get_current_player()
        assert player is not None
        assert player_id == replay.get_player_identifiers()[player]
        assert isinstance(move, str)
        play(replay, move)
    assert replay.__dict__ == game.__dict__


@pytest.mark.parametrize("stage", ["initial", "playing", "win", "draw"])
def test_public_views_keep_state_and_history_without_static_or_win_explanation_fields(
    stage,
):
    game = QuartoLogic()
    if stage == "playing":
        play(game, "give p")
        play(game, "place b2 give A")
    elif stage == "win":
        game = play_board(FINAL_WIN_BOARD)
    elif stage == "draw":
        game = play_board(DRAW_BOARD)
    state = sxpb.loads(game.render_player_view(0))
    full_view = sxpb.loads(game.render_player_full_sxpb(0))
    assert isinstance(state, dict)
    assert isinstance(full_view, dict)
    for view in (state, full_view):
        assert "columns" not in view
        assert "phase" not in view
        assert "piece_by_id" not in view
        assert "winning_line" not in view
        assert "winning_attributes" not in view
        if game.is_game_over():
            assert view["winner"] == game.winner
        else:
            assert "winner" not in view
        assert view["move_count"] == game.move_count
        assert "board" in view
    assert full_view["history"] == game.history.to_list()
    assert "moves" not in full_view
    precise = sxpb.loads(game.render_player_full_sxpb(0), precise=True)
    assert isinstance(precise, sxpb.Mesg)
    assert isinstance(precise["history"], sxpb.Many)


def test_cli_random_match_writes_report_and_trace(tmp_path):
    report = tmp_path / "report.sxpb"
    trace = tmp_path / "trace.jsonl"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "sxpb_game.harness.sxpb_game_main",
            "--game",
            "quarto",
            "--players",
            "(()) (() (algorithm random)) (() (algorithm random))",
            "--report_sxpb",
            str(report),
            "--trace_jsonl",
            str(trace),
        ],
        cwd=Path(__file__).resolve().parents[3],
        text=True,
        capture_output=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    parsed = sxpb.loads(report.read_text())
    assert isinstance(parsed, dict)
    assert parsed["report"]["game"] == "quarto"
    assert [player["id"] for player in parsed["report"]["players"]] == ["p1", "p2"]
    assert sorted(player["outcome"] for player in parsed["report"]["players"]) in [
        ["loss", "win"],
        ["draw", "draw"],
    ]
    assert "columns" not in parsed
    assert "phase" not in parsed
    assert "winning_line" not in parsed
    assert "winning_attributes" not in parsed
    assert parsed["winner"] in ("p1", "p2", "Draw")
    for player in parsed["report"]["players"]:
        expected_outcome = (
            "draw"
            if parsed["winner"] == "Draw"
            else "win"
            if player["id"] == parsed["winner"]
            else "loss"
        )
        assert player["outcome"] == expected_outcome
    assert "piece_by_id" not in parsed
    assert "moves" not in parsed
    assert len(parsed["history"]) == parsed["move_count"]
    precise = sxpb.loads(report.read_text(), precise=True)
    assert isinstance(precise, sxpb.Mesg)
    assert isinstance(precise["history"], sxpb.Many)
    assert all(
        isinstance(entry, sxpb.Lone) and len(entry) == 1 for entry in precise["history"]
    )
    assert "board" in parsed
    assert 5 <= parsed["move_count"] <= 17
    assert trace.stat().st_size > 0
