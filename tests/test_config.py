from pathlib import Path

import pytest
from pydantic import ValidationError

from eduagent.config import Settings

ENV_VARS = [
    "GEMINI_API_KEY", "GEMINI_MODEL", "GEMINI_DAILY_LIMIT", "QWEN_MODEL",
    "EMBED_MODEL", "OLLAMA_URL", "ROUTING_MODE", "DATA_DIR", "LOG_LEVEL",
    "OLLAMA_USE_GPU", "QWEN_TIMEOUT_S", "QWEN_NUM_CTX",
    "CHROMA_PORT", "HYBRID_ALPHA", "RERANK_ENABLED", "SEARCH_RESULTS", "SEARCH_RESULTS_QWEN",
    "SEARCH_MODULE_SHARE", "FORMULA_ENRICHMENT", "INGEST_THREADS", "MODELS_DIR",
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


@pytest.mark.parametrize(
    "name, value", [("QWEN_TIMEOUT_S", "0"), ("QWEN_TIMEOUT_S", "-1"), ("QWEN_NUM_CTX", "1024")]
)
def test_settings_reject_bad_timeout(monkeypatch, name, value):
    monkeypatch.setenv(name, value)
    with pytest.raises(ValidationError):
        make()


def test_kb_settings_defaults():
    s = make()
    assert s.chroma_port == 8001
    assert s.hybrid_alpha == 0.6
    assert s.rerank_enabled is True
    assert s.search_results == 10
    assert s.search_results_qwen == 6
    assert s.search_module_share == 0.7
    assert s.formula_enrichment is True
    assert s.ingest_threads == 4
    assert s.models_dir == Path("data/models")
    assert s.sources_dir == Path("data/sources")
    assert s.chroma_dir == Path("data/chroma")


@pytest.mark.parametrize(
    "name, value",
    [("HYBRID_ALPHA", "1.5"), ("SEARCH_MODULE_SHARE", "-0.1"), ("SEARCH_RESULTS", "0"), ("INGEST_THREADS", "0")],
)
def test_kb_settings_validation(monkeypatch, name, value):
    monkeypatch.setenv(name, value)
    with pytest.raises(ValidationError):
        make()
