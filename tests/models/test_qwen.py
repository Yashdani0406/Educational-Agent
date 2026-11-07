import pytest

from eduagent.config import Settings
from eduagent.models.qwen import qwen_complete, strip_think


def test_strip_think():
    assert strip_think("<think>hmm</think>\n tutor") == "tutor"
    assert strip_think("<think>unclosed tutor") == ""
    assert strip_think("plain text") == "plain text"


@pytest.mark.ollama
async def test_qwen_complete_live():
    text = await qwen_complete("Say hello in one word.", Settings(_env_file=None))
    assert text
    assert "<think>" not in text
