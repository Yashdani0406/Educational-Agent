from google.adk.agents import LlmAgent
from pydantic import SecretStr

from eduagent.team.registry import build_coordinator
from eduagent.config import Settings
from eduagent.db.database import Database
from eduagent.models.quota import QuotaTracker
from eduagent.models.router import ModelRouter
from eduagent.tracing.tracer import Tracer


async def fake(text, last_agent):
    return "tutor"


def test_build_coordinator_agents(tmp_path):
    db = Database(tmp_path / "study.db")
    db.migrate()
    settings = Settings(_env_file=None, gemini_api_key=None, data_dir=tmp_path)
    quota = QuotaTracker(db, 10)
    coord = build_coordinator(settings, ModelRouter(settings, quota), quota, Tracer(db), classify=fake)
    by_name = {a.name: a for a in coord.sub_agents}
    assert set(by_name) == {"tutor", "notes_maker", "coding", "analytics"}
    assert isinstance(by_name["tutor"], LlmAgent)
