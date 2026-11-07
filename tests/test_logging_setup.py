import logging

import pytest

from eduagent.config import Settings
from eduagent.logging_setup import configure_logging
from eduagent.tracing import current_trace_id

ENV_VARS = [
    "GEMINI_API_KEY", "GEMINI_MODEL", "GEMINI_DAILY_LIMIT", "QWEN_MODEL",
    "EMBED_MODEL", "OLLAMA_URL", "ROUTING_MODE", "DATA_DIR", "LOG_LEVEL",
]


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in ENV_VARS:
        monkeypatch.delenv(name, raising=False)


@pytest.fixture(autouse=True)
def restore_root():
    root = logging.getLogger()
    handlers, level = list(root.handlers), root.level
    yield
    for h in list(root.handlers):
        if h not in handlers:
            root.removeHandler(h)
            h.close()
    root.setLevel(level)


def make(tmp_path, **kw) -> Settings:
    return Settings(_env_file=None, data_dir=tmp_path, **kw)


def flush():
    for h in logging.getLogger().handlers:
        h.flush()


def read(path) -> str:
    flush()
    return path.read_text(encoding="utf-8")


def test_log_file_written(tmp_path):
    path = configure_logging(make(tmp_path))
    logging.getLogger("eduagent.x").info("hello")
    text = read(path)
    assert path == tmp_path / "logs" / "eduagent.log"
    assert "INFO" in text and "[eduagent.x]" in text and "hello" in text


def test_trace_id_in_line(tmp_path):
    path = configure_logging(make(tmp_path))
    log = logging.getLogger("eduagent.x")
    log.info("no trace")
    token = current_trace_id.set("abc123")
    try:
        log.info("with trace")
    finally:
        current_trace_id.reset(token)
    lines = read(path).splitlines()
    assert "trace=- no trace" in lines[0]
    assert "trace=abc123 with trace" in lines[1]


def test_secret_scrubbed_from_message_and_traceback(tmp_path):
    path = configure_logging(make(tmp_path, gemini_api_key="AIzaSECRET"))
    log = logging.getLogger("eduagent.x")
    log.info("calling with AIzaSECRET")
    try:
        raise ValueError("bad AIzaSECRET")
    except ValueError:
        log.exception("failed")
    text = read(path)
    assert "AIzaSECRET" not in text
    assert text.count("[redacted]") >= 2


def test_level_respected(tmp_path):
    path = configure_logging(make(tmp_path, log_level="WARNING"))
    log = logging.getLogger("eduagent.x")
    log.info("quiet-line")
    log.warning("loud-line")
    text = read(path)
    assert "quiet-line" not in text and "loud-line" in text


def test_debug_level_reaches_file(tmp_path):
    path = configure_logging(make(tmp_path, log_level="DEBUG"))
    logging.getLogger("eduagent.x").debug("deep-line")
    assert "deep-line" in read(path)


def test_configure_twice_no_duplicate_lines(tmp_path):
    s = make(tmp_path)
    configure_logging(s)
    path = configure_logging(s)
    logging.getLogger("eduagent.x").info("once-only")
    assert read(path).count("once-only") == 1


def test_foreign_handler_survives(tmp_path):
    foreign = logging.NullHandler()
    root = logging.getLogger()
    root.addHandler(foreign)
    try:
        configure_logging(make(tmp_path))
        configure_logging(make(tmp_path))
        assert foreign in root.handlers
    finally:
        root.removeHandler(foreign)


def test_noisy_libraries_quieted(tmp_path):
    configure_logging(make(tmp_path))
    assert logging.getLogger("litellm").level == logging.WARNING
