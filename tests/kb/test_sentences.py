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
