import time

import pytest

from eduagent.kb.sentences import split_sentences, word_count


def test_abbreviations_not_split():
    assert split_sentences("Trees, e.g. CART, split data. Fig. 3 shows it.") == [
        "Trees, e.g. CART, split data.",
        "Fig. 3 shows it.",
    ]


def test_decimals_and_initials():
    assert split_sentences("Accuracy rose to 0.93. J. R. Quinlan wrote ID3.") == [
        "Accuracy rose to 0.93.",
        "J. R. Quinlan wrote ID3.",
    ]


def test_question_and_newline_boundaries():
    assert split_sentences("Is it ready? Yes! Go on.") == ["Is it ready?", "Yes!", "Go on."]
    assert split_sentences("First heading\n\nSecond part") == ["First heading", "Second part"]
    assert split_sentences("This sentence is wrapped\nacross two lines.") == ["This sentence is wrapped\nacross two lines."]
    assert split_sentences("Steps:\n- load data\n* train model\n1. test it\n2) ship") == [
        "Steps:", "- load data", "* train model", "1. test it", "2) ship",
    ]


def test_closing_quotes_and_case_insensitive_abbreviation():
    assert split_sentences('He said "stop." Then left.') == ['He said "stop."', "Then left."]
    assert split_sentences("DR. Smith agreed. Done.") == ["DR. Smith agreed.", "Done."]


@pytest.mark.parametrize("text", [
    "Trees, e.g. CART, split data. Fig. 3 shows it.\r\nNext line\n\n\n  New para? Yes!",
    "A list:\n- one\n- two\n\nDone.",
    "Wrapped line\nstill going. Then 0.5 more.",
])
def test_no_text_added_or_lost(text):
    assert "".join("".join(split_sentences(text)).split()) == "".join(text.split())


@pytest.mark.parametrize("text", ["", "   \n\t\n"])
def test_empty_input(text):
    assert split_sentences(text) == []


def test_word_count():
    assert word_count("  three  little\nwords ") == 3
    assert word_count("") == 0


def test_numbered_line_in_hard_wrapped_sentence_is_not_cut():
    assert split_sentences("The answer was\n42. Then more text.") == ["The answer was\n42. Then more text."]


def test_year_at_line_start_ends_the_sentence_but_is_not_cut_before():
    assert split_sentences("It was published in\n1986. Later work followed.") == [
        "It was published in\n1986.",
        "Later work followed.",
    ]


def test_numbered_list_boundaries():
    assert split_sentences("Steps:\n1. load data\n2. train it\n3. test it") == [
        "Steps:", "1. load data", "2. train it", "3. test it",
    ]
    assert split_sentences("First point.\n2. second point") == ["First point.", "2. second point"]
    assert split_sentences("Really?\n3) third") == ["Really?", "3) third"]


def test_list_number_protection_outside_lists():
    # "5." opening a line is a list number, not a sentence end, so the real end after "text" still splits.
    assert split_sentences("See item\n5. in the text. Next one.") == ["See item\n5. in the text.", "Next one."]
    # but a number mid-line before a full stop does end a sentence
    assert split_sentences("It grew by 5. Then it fell.") == ["It grew by 5.", "Then it fell."]


def test_blank_line_with_crlf():
    assert split_sentences("First heading\r\n\r\nSecond part") == ["First heading", "Second part"]
    assert split_sentences("A\r\n  \r\nB") == ["A", "B"]


def test_long_single_line_is_fast_and_correct():
    n = 80_000 // 8
    text = " ".join(["The model splits data on the best feature."] * n)
    start = time.perf_counter()
    result = split_sentences(text)
    assert time.perf_counter() - start < 2
    assert len(result) == n


def test_long_punctuation_runs_are_fast():
    for text in ("." * 20_000 + " x", "x " + "?!" * 10_000 + " y", "." * 20_000 + "\" z. w"):
        start = time.perf_counter()
        split_sentences(text)
        assert time.perf_counter() - start < 1


@pytest.mark.parametrize("text", [
    "Wait... what? He said (loudly!) \"no.\" Then 'yes.' [See Fig. 2.] Done.",
    "Bullets:\n\u2022 one\n- two\n* three\nEnd.",
    "Steps:\r\n1. load\r\n2) train\r\n\r\nThe answer was\r\n42. Then more.",
    "It was published in\n1986. Later work followed.\nFirst point.\n2. second point",
    "Accuracy rose to 0.93. J. R. Quinlan wrote ID3. Dr. Who vs. Fig. 3, i.e. approx. five, etc. Done.",
])
def test_no_text_added_or_lost_varied(text):
    assert "".join("".join(split_sentences(text)).split()) == "".join(text.split())
