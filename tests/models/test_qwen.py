import litellm
import pytest

from eduagent.config import Settings
from eduagent.models.qwen import qwen_complete, strip_think


class _Reply:
    choices = [type("C", (), {"message": type("M", (), {"content": "hi"})()})()]


async def _kwargs_sent(monkeypatch, settings):
    seen = {}

    async def fake_acompletion(**kwargs):
        seen.update(kwargs)
        return _Reply()

    monkeypatch.setattr(litellm, "acompletion", fake_acompletion)
    await qwen_complete("hello", settings)
    return seen


async def test_qwen_complete_forces_cpu_by_default(monkeypatch):
    seen = await _kwargs_sent(monkeypatch, Settings(_env_file=None))
    assert seen["num_gpu"] == 0


async def test_qwen_complete_leaves_gpu_to_ollama_when_enabled(monkeypatch):
    seen = await _kwargs_sent(monkeypatch, Settings(_env_file=None, ollama_use_gpu=True))
    assert "num_gpu" not in seen


async def test_qwen_complete_sends_no_temperature_by_default(monkeypatch):
    seen = await _kwargs_sent(monkeypatch, Settings(_env_file=None))
    assert "temperature" not in seen


async def test_qwen_complete_passes_temperature(monkeypatch):
    seen = {}

    async def fake_acompletion(**kwargs):
        seen.update(kwargs)
        return _Reply()

    monkeypatch.setattr(litellm, "acompletion", fake_acompletion)
    await qwen_complete("hello", Settings(_env_file=None), temperature=0)
    assert seen["temperature"] == 0


def test_strip_think():
    assert strip_think("<think>hmm</think>\n tutor") == "tutor"
    assert strip_think("<think>unclosed tutor") == ""
    assert strip_think("reasoning only closed\n</think>\n\nhello") == "hello"
    assert strip_think("plain text") == "plain text"


@pytest.mark.ollama
async def test_qwen_complete_live():
    text = await qwen_complete("Say hello in one word.", Settings(_env_file=None))
    assert text
    assert "<think>" not in text


def test_ollama_options_include_num_ctx():
    from eduagent.models.qwen import ollama_options

    assert ollama_options(Settings(_env_file=None)) == {"num_ctx": 8192, "num_gpu": 0}
    assert ollama_options(Settings(_env_file=None, ollama_use_gpu=True)) == {"num_ctx": 8192}


async def test_qwen_complete_times_out(monkeypatch):
    import asyncio

    from eduagent.models.qwen import QwenTimeout

    async def slow(**kwargs):
        await asyncio.sleep(1)
        return _Reply()

    monkeypatch.setattr(litellm, "acompletion", slow)
    with pytest.raises(QwenTimeout, match="Qwen took longer than 0.05 s"):
        await qwen_complete("hello", Settings(_env_file=None, qwen_timeout_s=0.05))
