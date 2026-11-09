import pytest

from eduagent.agents.routing import (
    ROUTER_PROMPT,
    classifier_message,
    parse_mention,
    route,
)
from routing_cases import ROUTING_CASES


def fake(label):
    async def classify(text, last_agent):
        return label

    return classify


async def boom(text, last_agent):
    raise ConnectionError("ollama down")


def test_parse_mention():
    assert parse_mention("@Tutor explain x") == ("tutor", "explain x")
    assert parse_mention("@notes") == ("notes_maker", "")
    assert parse_mention("mail me@notes")[0] is None
    assert parse_mention("@foo hi") == (None, "@foo hi")


async def test_mention_beats_classifier():
    d = await route("@tutor explain x", None, fake("coding"))
    assert (d.agent, d.method, d.raw_label) == ("tutor", "mention", None)


async def test_code_fence_routes_coding():
    d = await route("what is this?\n```py\nx=1\n```", None, fake("tutor"))
    assert (d.agent, d.method, d.raw_label) == ("coding", "code", None)


async def test_attachment_routes_coding():
    d = await route("look", None, fake("tutor"), has_attachment=True)
    assert (d.agent, d.method) == ("coding", "code")


async def test_classifier_label_with_think_block():
    d = await route("how am I doing", None, fake("<think>hmm tutor</think> Analytics."))
    assert (d.agent, d.method) == ("analytics", "classifier")


async def test_classifier_garbage_defaults_to_last_agent():
    d = await route("hm", "coding", fake("banana"))
    assert (d.agent, d.method) == ("coding", "default")


async def test_classifier_garbage_defaults_to_tutor():
    d = await route("hm", None, fake("banana"))
    assert (d.agent, d.method) == ("tutor", "default")


async def test_classifier_exception_defaults():
    d = await route("hm", None, boom)
    assert (d.agent, d.method) == ("tutor", "default")


async def test_raw_label_recorded():
    d = await route("x", None, fake("<think>x</think> Coding."))
    assert d.raw_label == "Coding."


async def test_goal_text_with_agent_word_is_ignored():
    d = await route("x", None, fake("Goal: help with coding homework concepts\nAgent: tutor"))
    assert (d.agent, d.method) == ("tutor", "classifier")


async def test_agent_line_case_insensitive():
    d = await route("x", None, fake("Goal: x\nagent: Analytics."))
    assert d.agent == "analytics"


async def test_unknown_agent_line_defaults():
    d = await route("x", "coding", fake("Goal: notes\nAgent: banana"))
    assert (d.agent, d.method) == ("coding", "default")
    d = await route("x", None, fake("Goal: notes\nAgent: banana"))
    assert (d.agent, d.method) == ("tutor", "default")


async def test_raw_label_keeps_goal():
    d = await route("x", None, fake("Goal: a diagram\nAgent: tutor"))
    assert d.raw_label == "Goal: a diagram\nAgent: tutor"


async def test_classifier_sends_temperature_zero(monkeypatch):
    import litellm

    from eduagent.agents.routing import make_qwen_classifier
    from eduagent.config import Settings

    seen = {}

    class Reply:
        choices = [type("C", (), {"message": type("M", (), {"content": "Agent: tutor"})()})()]

    async def fake_acompletion(**kwargs):
        seen.update(kwargs)
        return Reply()

    monkeypatch.setattr(litellm, "acompletion", fake_acompletion)
    await make_qwen_classifier(Settings(_env_file=None))("hi", None)
    assert seen["temperature"] == 0


def test_classifier_message_format():
    assert classifier_message("why?", "tutor") == "Previous agent: tutor\nStudent message: why?"
    assert classifier_message("why?", None) == "Previous agent: none\nStudent message: why?"


def test_prompt_examples_not_in_eval_set():
    for message, _, _ in ROUTING_CASES:
        assert message not in ROUTER_PROMPT


def test_eval_set_covers_all_agents():
    assert {c[2] for c in ROUTING_CASES} == {"tutor", "notes_maker", "coding", "analytics"}
    assert len(ROUTING_CASES) == 45


@pytest.mark.parametrize("text", ["@tutor", "@CODE x"])
def test_mention_only_leading(text):
    assert parse_mention(text)[0] is not None
