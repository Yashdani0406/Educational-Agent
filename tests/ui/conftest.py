"""NiceGUI test setup: a user fixture that registers our pages on a throwaway Services."""

import os
from dataclasses import dataclass, field

import httpx2
import pytest
from nicegui import core, ui
from nicegui.testing.general import nicegui_reset_globals, prepare_simulation
from nicegui.testing.general_fixtures import pytest_configure  # noqa: F401
from nicegui.testing.user import User

from eduagent.team.routing import DISPLAY_NAMES
from eduagent.chat.service import AgentReply
from eduagent.config import Settings
from eduagent.db.courses import CoursesRepo
from eduagent.db.database import Database
from eduagent.db.threads import ThreadsRepo
from eduagent.models.quota import QuotaTracker
from eduagent.models.router import ModelRouter
from eduagent.services import Services
from eduagent.tracing.tracer import Tracer
from eduagent.ui.app import register_pages


@dataclass
class FakeChat:
    threads: ThreadsRepo
    sent: list = field(default_factory=list)
    resent: list = field(default_factory=list)
    canned_history: list = field(default_factory=list)

    async def new_thread(self, course_id):
        return self.threads.create(course_id)

    async def send(self, thread_id, text):
        self.sent.append((thread_id, text))
        return [AgentReply("analytics", "Analytics", f"echo: {text}", "qwen3:4b-instruct", "t1")]

    async def resend_to(self, thread_id, user_text, wrong, agent):
        self.resent.append((thread_id, user_text, wrong, agent))
        return [AgentReply(agent, DISPLAY_NAMES[agent], f"{agent} says hi", None, "t2")]

    async def history(self, thread_id):
        return self.canned_history


def make_services(tmp_path, warnings=None) -> Services:
    db = Database(tmp_path / "study.db")
    db.migrate()
    settings = Settings(_env_file=None, data_dir=tmp_path)
    quota = QuotaTracker(db, settings.gemini_daily_limit)
    threads = ThreadsRepo(db)
    return Services(
        settings, db, CoursesRepo(db), threads, quota, ModelRouter(settings, quota),
        Tracer(db), FakeChat(threads), list(warnings or []),
    )


@pytest.fixture
def build_services():
    return make_services


@pytest.fixture
def services(tmp_path):
    return make_services(tmp_path)


@pytest.fixture
def make_user():
    """Returns an async context manager factory: `async with make_user(services) as user`."""
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def run(services):
        with nicegui_reset_globals():
            os.environ["NICEGUI_USER_SIMULATION"] = "true"
            try:
                prepare_simulation()
                register_pages(services)
                ui.run(None, storage_secret="simulated secret")
                async with core.app.router.lifespan_context(core.app):
                    async with httpx2.AsyncClient(
                        transport=httpx2.ASGITransport(core.app), base_url="http://test"
                    ) as client:
                        yield User(client)
            finally:
                os.environ.pop("NICEGUI_USER_SIMULATION", None)

    return run


@pytest.fixture
async def user(services, make_user):
    async with make_user(services) as u:
        yield u
