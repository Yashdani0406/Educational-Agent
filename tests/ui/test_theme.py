import pytest

from eduagent.ui.theme import MASTERY, mastery_color


@pytest.mark.parametrize(
    ("score", "kind"),
    [(None, "untested"), (59.9, "weak"), (60, "okay"), (79.9, "okay"), (80, "strong")],
)
def test_mastery_color(score, kind):
    assert mastery_color(score) == MASTERY[kind]
