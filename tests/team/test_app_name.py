import logging

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

from eduagent.team.registry import build_coordinator
from eduagent.config import Settings
from eduagent.db.database import Database
from eduagent.models.quota import QuotaTracker
from eduagent.models.router import ModelRouter
from eduagent.services import APP_NAME
from eduagent.tracing.tracer import Tracer


async def fake(text, last_agent):
    return "tutor"


def test_no_app_name_mismatch_warning(tmp_path, monkeypatch, caplog):
    repo_root = next(p for p in __import__("pathlib").Path(__file__).resolve().parents if (p / "pyproject.toml").exists())
    monkeypatch.chdir(repo_root)
    db = Database(tmp_path / "study.db")
    db.migrate()
    settings = Settings(_env_file=None, gemini_api_key=None, data_dir=tmp_path)
    quota = QuotaTracker(db, 10)
    coord = build_coordinator(settings, ModelRouter(settings, quota), quota, Tracer(db), classify=fake)
    with caplog.at_level(logging.WARNING):
        Runner(app_name=APP_NAME, agent=coord, session_service=InMemorySessionService())
    assert "App name mismatch" not in caplog.text
    assert APP_NAME == "eduagent"
