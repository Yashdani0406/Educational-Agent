from datetime import UTC, datetime

import pytest
from pydantic import SecretStr

from eduagent.config import Settings
from eduagent.db.database import Database
from eduagent.models.quota import QuotaTracker
from eduagent.models.router import ModelRouter


def make(tmp_path, mode, exhausted):
    db = Database(tmp_path / "study.db")
    db.migrate()
    quota = QuotaTracker(db, 10, lambda: datetime(2026, 11, 7, 12, tzinfo=UTC))
    if exhausted:
        quota.mark_exhausted()
    settings = Settings(
        _env_file=None, gemini_api_key=SecretStr("k"), routing_mode=mode,
        gemini_model="gem", qwen_model="qw", data_dir=tmp_path,
    )
    return ModelRouter(settings, quota)


CASES = [
    # mode, job, exhausted, provider, reason
    ("all_qwen", "chat", False, "qwen", "mode"),
    ("all_qwen", "heavy", True, "qwen", "mode"),
    ("all_qwen", "light", False, "qwen", "mode"),
    ("split", "chat", False, "gemini", "job split"),
    ("split", "heavy", False, "gemini", "job split"),
    ("split", "chat", True, "qwen", "gemini quota exhausted"),
    ("split", "heavy", True, "qwen", "gemini quota exhausted"),
    ("split", "light", False, "qwen", "job split"),
    ("split", "light", True, "qwen", "job split"),
    ("all_gemini", "chat", False, "gemini", "mode"),
    ("all_gemini", "heavy", False, "gemini", "mode"),
    ("all_gemini", "light", False, "gemini", "mode"),
    ("all_gemini", "chat", True, "qwen", "gemini quota exhausted"),
    ("all_gemini", "heavy", True, "qwen", "gemini quota exhausted"),
    ("all_gemini", "light", True, "qwen", "gemini quota exhausted"),
]


@pytest.mark.parametrize("mode,job,exhausted,provider,reason", CASES)
def test_choose_table(tmp_path, mode, job, exhausted, provider, reason):
    choice = make(tmp_path, mode, exhausted).choose(job)
    assert choice.provider == provider
    assert choice.reason == reason
    assert choice.model_id == ("gem" if provider == "gemini" else "qw")


def test_no_key_forces_qwen(tmp_path):
    db = Database(tmp_path / "study.db")
    db.migrate()
    settings = Settings(_env_file=None, gemini_api_key=None, routing_mode="all_gemini",
                        data_dir=tmp_path)
    choice = ModelRouter(settings, QuotaTracker(db, 10)).choose("chat")
    assert choice.provider == "qwen"


def test_choose_log_flag(tmp_path, caplog):
    router = make(tmp_path, "split", False)
    with caplog.at_level("INFO", logger="eduagent.models.router"):
        router.choose("chat", log=False)
        assert caplog.records == []
        router.choose("chat")
    assert [r.getMessage() for r in caplog.records] == ["route job=chat -> gem (job split)"]
