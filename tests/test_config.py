from pathlib import Path

import pytest
from pydantic import ValidationError

from eduagent.config import Settings

ENV_VARS = [
    "GEMINI_API_KEY", "GEMINI_MODEL", "GEMINI_DAILY_LIMIT", "QWEN_MODEL",
    "EMBED_MODEL", "OLLAMA_URL", "ROUTING_MODE", "DATA_DIR", "LOG_LEVEL",
    "OLLAMA_USE_GPU",
]


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in ENV_VARS:
        monkeypatch.delenv(name, raising=False)


def make() -> Settings:
    return Settings(_env_file=None)


def test_defaults():
    s = make()
    assert s.routing_mode == "split"
    assert s.qwen_model == "qwen3:4b-instruct"
    assert s.db_path == Path("data/study.db")
    assert s.log_level == "INFO"
    assert s.log_dir == Path("data/logs")
    assert s.ollama_use_gpu is False


def test_sessions_db_url():
    assert make().sessions_db_url == "sqlite+aiosqlite:///data/sessions.db"


def test_no_key_forces_all_qwen(monkeypatch):
    monkeypatch.setenv("ROUTING_MODE", "split")
    assert make().effective_routing_mode == "all_qwen"


@pytest.mark.parametrize("blank", ["", "   "])
def test_blank_key_counts_as_no_key(monkeypatch, blank):
    monkeypatch.setenv("GEMINI_API_KEY", blank)
    monkeypatch.setenv("ROUTING_MODE", "all_gemini")
    assert make().effective_routing_mode == "all_qwen"


def test_key_keeps_mode(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "sk-test")
    monkeypatch.setenv("ROUTING_MODE", "all_gemini")
    assert make().effective_routing_mode == "all_gemini"


def test_invalid_mode_rejected(monkeypatch):
    monkeypatch.setenv("ROUTING_MODE", "fast")
    with pytest.raises(ValidationError):
        make()


def test_key_not_in_repr(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "sk-test")
    assert "sk-test" not in repr(make())
