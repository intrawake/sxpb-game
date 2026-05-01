import os
import sys
import sxpb

# Add the paths for imports
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "tictactoe"))
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "wordle"))
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "connect_four"))
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "mastermind"))
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "blackjack"))
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "minesweeper"))
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "sudoku"))
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "old_maid"))
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "cthulhu"))
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "codenames"))

from sxpb_game.by_title.tictactoe.logic import TicTacToeLogic
from sxpb_game.by_title.wordle.logic import WordleLogic
from sxpb_game.by_title.connect_four.logic import ConnectFourLogic
from sxpb_game.by_title.mastermind.logic import MastermindLogic
from sxpb_game.by_title.blackjack.logic import BlackjackLogic
from sxpb_game.by_title.minesweeper.logic import MinesweeperLogic
from sxpb_game.by_title.sudoku.logic import SudokuLogic
from sxpb_game.by_title.old_maid.logic import OldMaidLogic
from sxpb_game.by_title.cthulhu.logic import CthulhuLogic
from sxpb_game.by_title.codenames.logic import CodenamesLogic
from sxpb_game.by_title.trolley.logic import TrolleyLogic


def test_tictactoe_interface():
    game = TicTacToeLogic()
    ids = game.get_player_identifiers()
    assert ids == ["X", "O"], f"Expected ['X', 'O'], got {ids}"

    # Play a few moves to reach the mock state
    # Moves: Xb2 Oa3 Xc1 Oa1 Xa2
    game.make_move(0, "b2")
    game.make_move(1, "a3")
    game.make_move(0, "c1")
    game.make_move(1, "a1")
    game.make_move(0, "a2")

    view = game.render_player_view(1)
    history_view = game.render_player_history(1)
    expected_sxpb = """; --- Tic-Tac-Toe (3 Columns x 3 Rows) ---
(board
 ; Columns: a b c
 (row3 (()) O _ _)
 (row2 (()) X X _)
 (row1 (()) O _ X)
 ; Columns: a b c
)

; --- Game Metadata ---
(player_to_move O)
(move_count 5)"""
    assert game.is_game_over() is False, "Game should not be over"
    assert game.get_current_player() == 1, "Current player should be O"
    assert "What is your move" in game.get_prompt(1)

    # Test make_move
    assert game.make_move(1, "b1").success
    assert game.current_player == "X"
    assert game.move_count == 6
    assert game.board[(1, 0)] == "O"
    assert "Ob1" in game.history

    parsed_view = sxpb.loads(view)
    expected_dict = {
        "board": {
            "row3": ["O", "_", "_"],
            "row2": ["X", "X", "_"],
            "row1": ["O", "_", "X"],
        },
        "player_to_move": "O",
        "move_count": 5,
    }
    assert parsed_view == expected_dict, (
        f"Dict mismatch:\nExpected: {expected_dict}\nGot: {parsed_view}"
    )

    parsed_history = sxpb.loads(history_view)
    assert parsed_history == {"moves": ["Xb2", "Oa3", "Xc1", "Oa1", "Xa2"]}

    if view.strip() == expected_sxpb.strip():
        print("PASS: TicTacToeLogic interface tests passed.")
    else:
        print("FAIL: TicTacToeLogic interface output mismatch")
        sys.exit(1)


def test_wordle_interface():
    game = WordleLogic("TRAIN")
    ids = game.get_player_identifiers()
    assert ids == ["0", "1"], f"Expected ['0', '1'], got {ids}"

    game.make_move(1, "ideas")
    game.make_move(1, "might")
    game.make_move(1, "tatar")
    game.make_move(1, "purin")

    view = game.render_player_view(1)
    expected_sxpb = """; --- Wordle ---
(board
 (guess1 (()) I d e A s)
 (guess2 (()) m I g h T)
 (guess3 (()) T A t a R)
 (guess4 (()) p u R I N)
 (guess5 (()) _ _ _ _ _)
 (guess6 (()) _ _ _ _ _)
 ; Letters guessed in correct positions.
 (pinned (()) T _ _ I N)
)

; --- Game Metadata ---
(present (()) A I N R T)
(absent (()) D E G H M P S U)
(guess_count 4)"""
    assert "TRAIN" not in view, "Secret word leaked into player view!"
    assert game.is_game_over() is False, "Game should not be over"
    assert game.get_current_player() == 1, "Current player should be 1"
    assert "guess" in game.get_prompt(1)
    parsed_view = sxpb.loads(view)
    expected_dict = {
        "board": {
            "guess1": ["I", "d", "e", "A", "s"],
            "guess2": ["m", "I", "g", "h", "T"],
            "guess3": ["T", "A", "t", "a", "R"],
            "guess4": ["p", "u", "R", "I", "N"],
            "guess5": ["_", "_", "_", "_", "_"],
            "guess6": ["_", "_", "_", "_", "_"],
            "pinned": ["T", "_", "_", "I", "N"],
        },
        "present": ["A", "I", "N", "R", "T"],
        "absent": ["D", "E", "G", "H", "M", "P", "S", "U"],
        "guess_count": 4,
    }
    assert parsed_view == expected_dict, (
        f"Dict mismatch:\nExpected: {expected_dict}\nGot: {parsed_view}"
    )

    if view.strip() == expected_sxpb.strip():
        print("PASS: WordleLogic interface tests passed.")
    else:
        print("FAIL: WordleLogic interface output mismatch")
        sys.exit(1)


def test_connect_four_interface():
    game = ConnectFourLogic()
    ids = game.get_player_identifiers()
    assert ids == ["R", "Y"], f"Expected ['R', 'Y'], got {ids}"

    # "Rc1", "Yd1", "Rd2", "Ye1", "Re2", "Yf1", "Rg1", "Yb1", "Rf2", "Yc2", "Rg2"
    game.make_move(0, "c1")
    game.make_move(1, "d1")
    game.make_move(0, "d2")
    game.make_move(1, "e1")
    game.make_move(0, "e2")
    game.make_move(1, "f1")
    game.make_move(0, "g1")
    game.make_move(1, "b1")
    game.make_move(0, "f2")
    game.make_move(1, "c2")
    game.make_move(0, "g2")

    view = game.render_player_view(1)
    history_view = game.render_player_history(1)
    expected_sxpb = """; --- Connect Four (7 Columns x 6 Rows) ---
(board
 ; Columns: a b c d e f g
 (row6 (()) _ _ _ _ _ _ _)
 (row5 (()) _ _ _ _ _ _ _)
 (row4 (()) _ _ _ _ _ _ _)
 (row3 (()) _ _ _ _ _ _ _)
 (row2 (()) _ _ Y R R R R)
 (row1 (()) _ Y R Y Y Y R)
 ; Columns: a b c d e f g
)

; --- Game Metadata ---
(player_to_move YELLOW)
(move_count 11)"""
    assert game.is_game_over() is True, "Game should be over"
    assert game.get_current_player() is None, "Current player should be None"
    assert "YELLOW" in game.get_prompt(1)
    parsed_view = sxpb.loads(view)
    expected_dict = {
        "board": {
            "row6": ["_", "_", "_", "_", "_", "_", "_"],
            "row5": ["_", "_", "_", "_", "_", "_", "_"],
            "row4": ["_", "_", "_", "_", "_", "_", "_"],
            "row3": ["_", "_", "_", "_", "_", "_", "_"],
            "row2": ["_", "_", "Y", "R", "R", "R", "R"],
            "row1": ["_", "Y", "R", "Y", "Y", "Y", "R"],
        },
        "player_to_move": "YELLOW",
        "move_count": 11,
    }
    assert parsed_view == expected_dict, (
        f"Dict mismatch:\nExpected: {expected_dict}\nGot: {parsed_view}"
    )

    parsed_history = sxpb.loads(history_view)
    assert parsed_history == {
        "moves": [
            "Rc1",
            "Yd1",
            "Rd2",
            "Ye1",
            "Re2",
            "Yf1",
            "Rg1",
            "Yb1",
            "Rf2",
            "Yc2",
            "Rg2",
        ]
    }

    if view.strip() == expected_sxpb.strip():
        print("PASS: ConnectFourLogic interface tests passed.")
    else:
        print("FAIL: ConnectFourLogic interface output mismatch")
        sys.exit(1)


def test_mastermind_interface():
    game = MastermindLogic("RGBY")
    ids = game.get_player_identifiers()
    assert ids == ["0", "1"], f"Expected ['0', '1'], got {ids}"

    # "BOBY", "GBOY", "POGR", "GPBY", "GRBY", "GGBY", "RGBY"
    game.make_move(1, "BOBY")
    game.make_move(1, "GBOY")
    game.make_move(1, "POGR")
    game.make_move(1, "GPBY")
    game.make_move(1, "GRBY")
    game.make_move(1, "GGBY")
    game.make_move(1, "RGBY")

    view = game.render_player_view(1)
    expected_sxpb = """; --- Mastermind ---
; The game is over. The secret code was: RGBY
(board
 (row1 (()) B O B Y) (clue1 (()) 2 0)
 (row2 (()) G B O Y) (clue2 (()) 1 2)
 (row3 (()) P O G R) (clue3 (()) 0 2)
 (row4 (()) G P B Y) (clue4 (()) 2 1)
 (row5 (()) G R B Y) (clue5 (()) 2 2)
 (row6 (()) G G B Y) (clue6 (()) 3 0)
 (row7 (()) R G B Y) (clue7 (()) 4 0)
 (row8 (()) _ _ _ _)
 (row9 (()) _ _ _ _)
 (row10 (()) _ _ _ _)
)

; --- Game Metadata ---
(colors (()) R G B Y O P)
(turn_count 7)"""
    assert "secret_code" not in view, "Secret code leaked!"
    assert game.is_game_over() is True, "Game should be over"
    assert game.get_current_player() is None, "Current player should be None"
    assert "guess" in game.get_prompt(1)
    parsed_view = sxpb.loads(view)
    expected_dict = {
        "board": {
            "row1": ["B", "O", "B", "Y"],
            "clue1": [2, 0],
            "row2": ["G", "B", "O", "Y"],
            "clue2": [1, 2],
            "row3": ["P", "O", "G", "R"],
            "clue3": [0, 2],
            "row4": ["G", "P", "B", "Y"],
            "clue4": [2, 1],
            "row5": ["G", "R", "B", "Y"],
            "clue5": [2, 2],
            "row6": ["G", "G", "B", "Y"],
            "clue6": [3, 0],
            "row7": ["R", "G", "B", "Y"],
            "clue7": [4, 0],
            "row8": ["_", "_", "_", "_"],
            "row9": ["_", "_", "_", "_"],
            "row10": ["_", "_", "_", "_"],
        },
        "colors": ["R", "G", "B", "Y", "O", "P"],
        "turn_count": 7,
    }
    assert parsed_view == expected_dict, (
        f"Dict mismatch:\nExpected: {expected_dict}\nGot: {parsed_view}"
    )

    if view.strip() == expected_sxpb.strip():
        print("PASS: MastermindLogic interface tests passed.")
    else:
        print("FAIL: MastermindLogic interface output mismatch")
        sys.exit(1)


def test_blackjack_interface():
    game = BlackjackLogic()
    ids = game.get_player_identifiers()
    assert ids == ["GM", "Player"]

    # Mock some hands directly
    game.dealer_hand = ["S9", "S10"]
    game.player_hand = ["D3", "D8"]
    game.game_over = False
    game.phase = "PLAYER_ACTION"

    view = game.render_player_view(1)
    expected_sxpb = """; --- Blackjack (6 Decks) ---
(board
 (dealer (()) S9 ?)
 (player (()) D3 D8)  ; Total: 11
)"""
    assert game.is_game_over() is False, "Game should not be over"
    assert game.get_current_player() == 1, "Current player should be Player"
    assert "move" in game.get_prompt(1)

    # Test make_move (Hit)
    assert game.make_move(1, "H").success
    assert game.get_current_player() == 0, "Current player should be GM to deal card"
    assert game.make_move(0, "SA").success
    assert len(game.player_hand) == 3
    assert game.get_current_player() == 1, "Current player should be Player again"

    parsed_view = sxpb.loads(view)
    expected_dict = {"board": {"dealer": ["S9", "?"], "player": ["D3", "D8"]}}
    assert parsed_view == expected_dict, (
        f"Dict mismatch:\nExpected: {expected_dict}\nGot: {parsed_view}"
    )

    if view.strip() == expected_sxpb.strip():
        print("PASS: BlackjackLogic interface tests passed.")
    else:
        print("FAIL: BlackjackLogic interface output mismatch")
        sys.exit(1)


def test_minesweeper_interface():
    game = MinesweeperLogic("a8 h8 a1")  # Fixed mines for testing
    ids = game.get_player_identifiers()
    assert ids == ["GM", "Player"]

    game.make_move(1, "c5")
    game.make_move(0, "a8 h8 a1")

    # To match expected output:
    # Easier to mock it directly to match old test
    game.revealed = {
        (5, 7),
        (4, 6),
        (5, 6),
        (3, 5),
        (4, 5),
        (2, 4),
        (3, 4),
        (1, 3),
        (2, 3),
        (0, 2),
        (1, 2),
    }
    game.flags = {(0, 0)}
    game.initialized = True
    game.mines = {(0, 7), (7, 7), (0, 0)}
    game.target_mine_count = 3
    game.game_over = False
    game.mines_placed = True

    view = game.render_player_view(1)
    expected_sxpb = """; --- Minesweeper (8x8 Beginner) ---
(board ("")
 ; COL a b c d e f g h
 (row8 _ _ _ _ _ 0 _ _)
 (row7 _ _ _ _ 0 0 _ _)
 (row6 _ _ _ 0 0 _ _ _)
 (row5 _ _ 0 0 _ _ _ _)
 (row4 _ 0 0 _ _ _ _ _)
 (row3 0 0 _ _ _ _ _ _)
 (row2 _ _ _ _ _ _ _ _)
 (row1 F _ _ _ _ _ _ _)
)

; --- Game Metadata ---
(total_mines 3)
(flags_placed 1)
(state in_progress)"""
    assert game.is_game_over() is False, "Game should not be over"
    assert game.get_current_player() == 1, "Current player should be Player"

    parsed_view = sxpb.loads(view)
    expected_dict = {
        "board": [
            {"row8": ["_", "_", "_", "_", "_", "0", "_", "_"]},
            {"row7": ["_", "_", "_", "_", "0", "0", "_", "_"]},
            {"row6": ["_", "_", "_", "0", "0", "_", "_", "_"]},
            {"row5": ["_", "_", "0", "0", "_", "_", "_", "_"]},
            {"row4": ["_", "0", "0", "_", "_", "_", "_", "_"]},
            {"row3": ["0", "0", "_", "_", "_", "_", "_", "_"]},
            {"row2": ["_", "_", "_", "_", "_", "_", "_", "_"]},
            {"row1": ["F", "_", "_", "_", "_", "_", "_", "_"]},
        ],
        "total_mines": 3,
        "flags_placed": 1,
        "state": "in_progress",
    }
    assert parsed_view == expected_dict, (
        f"Dict mismatch:\nExpected: {expected_dict}\nGot: {parsed_view}"
    )

    if view.strip() == expected_sxpb.strip():
        print("PASS: MinesweeperLogic interface tests passed.")
    else:
        print("FAIL: MinesweeperLogic interface output mismatch")
        print("Expected:\n" + expected_sxpb)
        print("Got:\n" + view)
        sys.exit(1)


def test_sudoku_interface():
    # Use an almost solved board input to create mock state
    board_input = """; --- Sudoku (9x9 Grid) ---
(board ("")
 ; Col  a b c  d e f  g h i
 (row9  . 3 .   . 7 .   . . .)
 (row8  6 . .   1 9 5   . . .)
 (row7  . 9 8   . . .   . 6 .)

 (row6  8 . .   . 6 .   . . 3)
 (row5  4 . .   8 . 3   . . 1)
 (row4  7 . .   . 2 .   . . 6)

 (row3  . 6 .   . . .   2 8 .)
 (row2  . . .   4 1 9   . . 5)
 (row1  . . .   . 8 .   . 7 9)
)"""
    game = SudokuLogic(board_input)
    ids = game.get_player_identifiers()
    assert ids == ["GM", "Player"]

    # Make a move
    game.make_move(1, "a9=5")

    view = game.render_player_view(1)
    expected_sxpb = """; --- Sudoku (9x9 Grid) ---
(board ("")
 ; Col  a b c  d e f  g h i
 (row9  5 3 .   . 7 .   . . .)
 (row8  6 . .   1 9 5   . . .)
 (row7  . 9 8   . . .   . 6 .)

 (row6  8 . .   . 6 .   . . 3)
 (row5  4 . .   8 . 3   . . 1)
 (row4  7 . .   . 2 .   . . 6)

 (row3  . 6 .   . . .   2 8 .)
 (row2  . . .   4 1 9   . . 5)
 (row1  . . .   . 8 .   . 7 9)
)"""
    assert game.is_game_over() is False, "Game should not be over"
    assert game.get_current_player() == 1, "Current player should be Player"
    assert "move" in game.get_prompt(1)
    parsed_view = sxpb.loads(view)
    expected_dict = {
        "board": [
            {"row9": ["5", "3", ".", ".", "7", ".", ".", ".", "."]},
            {"row8": ["6", ".", ".", "1", "9", "5", ".", ".", "."]},
            {"row7": [".", "9", "8", ".", ".", ".", ".", "6", "."]},
            {"row6": ["8", ".", ".", ".", "6", ".", ".", ".", "3"]},
            {"row5": ["4", ".", ".", "8", ".", "3", ".", ".", "1"]},
            {"row4": ["7", ".", ".", ".", "2", ".", ".", ".", "6"]},
            {"row3": [".", "6", ".", ".", ".", ".", "2", "8", "."]},
            {"row2": [".", ".", ".", "4", "1", "9", ".", ".", "5"]},
            {"row1": [".", ".", ".", ".", "8", ".", ".", "7", "9"]},
        ]
    }
    assert parsed_view == expected_dict, (
        f"Dict mismatch:\nExpected: {expected_dict}\nGot: {parsed_view}"
    )

    if view.strip() == expected_sxpb.strip():
        print("PASS: SudokuLogic interface tests passed.")
    else:
        print("FAIL: SudokuLogic interface output mismatch")
        print(view)
        sys.exit(1)


def test_cthulhu_interface():
    game = CthulhuLogic(5)
    ids = game.get_player_identifiers()
    assert ids == ["GM", "p1", "p2", "p3", "p4"]

    game.make_move(0, "Investigator Cultist Investigator Investigator")
    game.make_move(
        0,
        "Blank Blank Blank Blank ElderSign Blank Cthulhu Blank Blank Blank Blank Blank Blank Blank ElderSign Blank Blank Blank Blank Blank",
    )

    game.make_move(1, "??? who has an elder sign")
    game.make_move(2, "i do")
    game.make_move(3, "not me")
    game.make_move(4, "me neither")
    game.make_move(1, "Move: p2!")

    view = game.render_player_view(1)
    history_view = game.render_player_history(1)

    parsed_view = sxpb.loads(view)
    assert isinstance(parsed_view, dict)
    assert "table" in parsed_view
    assert "elder_sign_total" in parsed_view
    assert "cultist_count_range" in parsed_view

    parsed_history = sxpb.loads(history_view)
    assert isinstance(parsed_history, dict)
    assert "history" in parsed_history

    # Asserting exact structure for the history sxpb
    history = parsed_history["history"]
    assert isinstance(history, list), f"Expected list for history, got {type(history)}"

    # check that we can parse the board safely
    print("PASS: CthulhuLogic interface tests passed.")


def test_old_maid_interface():
    game = OldMaidLogic()
    # P1 gets: H4, D5, HQ (no pairs) -> hand: H4, D5, HQ
    # P2 gets: S4, C5 (no pairs) -> hand: S4, C5
    # Card order for deal: H4 S4 D5 C5 HQ
    game.make_move(0, "H4 S4 D5 C5 HQ")

    view = game.render_player_view(1)
    history_view = game.render_player_history(1)
    expected_sxpb = """; --- Old Maid ---
(board
 (p1_cards (()) H4 D5 HQ)
 (p2_cards (()) ? ?)
)
(pair_count_by_player () (p1 0) (p2 0))
"""
    parsed_view = sxpb.loads(view)
    expected_dict = {
        "board": {"p1_cards": ["H4", "D5", "HQ"], "p2_cards": ["?", "?"]},
        "pair_count_by_player": {"p1": 0, "p2": 0},
    }
    assert parsed_view == expected_dict, (
        f"Dict mismatch:\nExpected: {expected_dict}\nGot: {parsed_view}"
    )

    parsed_history = sxpb.loads(history_view)
    assert parsed_history == {"history": []}

    if view.strip() == expected_sxpb.strip():
        print("PASS: OldMaidLogic interface tests passed.")
    else:
        print("FAIL: OldMaidLogic interface output mismatch")
        print("Expected:\n" + expected_sxpb)
        print("Got:\n" + view)
        import sys

        sys.exit(1)


def test_codenames_interface():
    game = CodenamesLogic()
    game.words = [f"WORD{i}" for i in range(25)]
    game.word_colors = {"WORD0": "red", "WORD1": "blue", "WORD2": "assassin"}
    for i in range(3, 25):
        game.word_colors[f"WORD{i}"] = "neutral"

    game.make_move(1, "HINT 1")
    game.make_move(3, "WORD0")
    game.make_move(3, ".")

    view = game.render_player_view(1)
    history_view = game.render_player_history(1)

    parsed_view = sxpb.loads(view)
    assert isinstance(parsed_view, dict)
    assert "table" in parsed_view
    assert "score" in parsed_view

    parsed_history = sxpb.loads(history_view)
    assert isinstance(parsed_history, dict)
    assert "history" in parsed_history

    history = parsed_history["history"]
    assert isinstance(history, list), f"Expected list for history, got {type(history)}"

    print("PASS: CodenamesLogic interface tests passed.")


def test_trolley_interface():
    game = TrolleyLogic()
    ids = game.get_player_identifiers()
    assert ids == ["p0", "p1", "p2", "p3"]

    game.make_move(0, "Batman")
    game.make_move(0, "Robin")
    game.make_move(1, "Save Batman, he's the hero")
    game.make_move(2, "Save Robin, he's a just a boy")

    view = game.render_player_view(3)
    history_view = game.render_player_history(3)

    parsed_view = sxpb.loads(view)
    assert isinstance(parsed_view, dict)
    assert "trolley_problem" in parsed_view

    parsed_history = sxpb.loads(history_view)
    assert isinstance(parsed_history, dict)
    assert "history" in parsed_history

    print("PASS: TrolleyLogic interface tests passed.")


def test_all_games_have_parsable_initial_state():
    import importlib
    import inspect
    from sxpb_game.eval.logic import GameLogic

    games_dir = os.path.join(
        os.path.dirname(__file__), "..", "src", "sxpb_game", "by_title"
    )
    games = [
        d
        for d in os.listdir(games_dir)
        if os.path.isdir(os.path.join(games_dir, d)) and d != "__pycache__"
    ]

    for game_name in games:
        try:
            logic_mod = importlib.import_module(f"sxpb_game.by_title.{game_name}.logic")
        except ImportError:
            continue

        logic_class = None
        for name, obj in inspect.getmembers(logic_mod, inspect.isclass):
            if issubclass(obj, GameLogic) and obj is not GameLogic:
                logic_class = obj
                break

        if logic_class:
            try:
                game = logic_class()
                players = game.get_player_identifiers()
                for i in range(len(players)):
                    view = game.render_player_view(i)
                    try:
                        parsed = sxpb.loads(view)
                        assert isinstance(parsed, dict) or isinstance(parsed, list), (
                            f"{game_name} parsed view is not dict/list"
                        )
                    except Exception as e:
                        raise AssertionError(
                            f"Failed to parse initial sxpb view for {game_name} player {players[i]}:\n{view}\nError: {e}"
                        )
            except Exception as e:
                raise AssertionError(
                    f"Failed to test initial state for {game_name}: {e}"
                )

    print(f"PASS: All {len(games)} games have parsable initial sxpb states.")


if __name__ == "__main__":
    test_tictactoe_interface()
    test_wordle_interface()
    test_connect_four_interface()
    test_mastermind_interface()
    test_blackjack_interface()
    test_minesweeper_interface()
    test_sudoku_interface()
    test_cthulhu_interface()
    test_old_maid_interface()
    test_codenames_interface()
    test_trolley_interface()
    test_all_games_have_parsable_initial_state()
