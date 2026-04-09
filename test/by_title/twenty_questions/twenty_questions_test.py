from sxpb_game.by_title.twenty_questions.logic import TwentyQuestionsLogic


def test_game_flow():
    game = TwentyQuestionsLogic()
    assert game.get_current_player() == 0

    # Oracle chooses word
    res = game.make_move(0, "The secret word is apple.")
    assert res.success
    assert game.secret_word == "apple"
    assert game.get_current_player() == 1

    # Guesser asks a question
    res = game.make_move(1, "Is it a fruit?")
    assert res.success
    assert game.phase == "answer_question"
    assert game.get_current_player() == 0

    # Oracle answers
    res = game.make_move(0, "yes")
    assert res.success
    assert game.phase == "ask_question"
    assert game.get_current_player() == 1
    assert game.questions_asked == 1

    # Guesser asks another question
    res = game.make_move(1, "Is it a banana?")
    assert res.success

    # Oracle answers no
    res = game.make_move(0, "nope it is not")
    assert res.success
    assert game.questions_asked == 2

    # Guesser asks something vague
    res = game.make_move(1, "Is it a red?")
    assert res.success

    # Oracle answers usually
    res = game.make_move(0, "usually")
    assert res.success
    assert game.questions_asked == 3

    # Guesser asks a weird question
    res = game.make_move(1, "Is it from space?")
    assert res.success

    # Oracle doesn't know
    res = game.make_move(0, "idk")
    assert res.success
    # The counter should go down because it was incremented when asking, but reverted on 'idk'
    assert game.questions_asked == 3

    # Guesser guesses correctly
    res = game.make_move(1, "Is it an apple?")
    assert res.success
    assert game.is_game_over()
    assert game.winner == 1


def test_oracle_wins():
    game = TwentyQuestionsLogic()
    game.max_questions = 2

    game.make_move(0, "banana")

    game.make_move(1, "Is it round?")
    game.make_move(0, "yes")

    game.make_move(1, "Is it an orange?")
    game.make_move(0, "no")

    assert game.is_game_over()
    assert game.winner == 0
