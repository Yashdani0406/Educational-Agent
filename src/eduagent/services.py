"""Builds every long-lived service the app uses, wired together."""

import logging
from dataclasses import dataclass, field

from google.adk.runners import Runner
from google.adk.sessions import DatabaseSessionService

from eduagent.agents.registry import build_coordinator
from eduagent.chat.service import ChatService
from eduagent.config import Settings
from eduagent.db.courses import CoursesRepo
from eduagent.db.database import Database
from eduagent.db.threads import ThreadsRepo
from eduagent.models.quota import QuotaTracker
from eduagent.models.router import ModelRouter
from eduagent.tracing.tracer import Tracer

log = logging.getLogger(__name__)

WHAT_IT_DOES = "Creates the database, models, agents and chat service the app runs on."

APP_NAME = "eduagent"


@dataclass
class Services:
    settings: Settings
    db: Database
    courses: CoursesRepo
    threads: ThreadsRepo
    quota: QuotaTracker
    router: ModelRouter
    tracer: Tracer
    chat: ChatService
    warnings: list[str] = field(default_factory=list)


def build_services(settings: Settings) -> Services:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    db = Database(settings.db_path)
    db.migrate()
    key = settings.gemini_api_key.get_secret_value() if settings.gemini_api_key else ""
    tracer = Tracer(db, secrets=[key] if key else [])
    quota = QuotaTracker(db, settings.gemini_daily_limit)
    router = ModelRouter(settings, quota)
    coordinator = build_coordinator(settings, router, quota, tracer)
    sessions = DatabaseSessionService(settings.sessions_db_url)
    runner = Runner(app_name=APP_NAME, agent=coordinator, session_service=sessions)
    threads = ThreadsRepo(db)
    chat = ChatService(runner, sessions, threads, tracer, APP_NAME)
    return Services(settings, db, CoursesRepo(db), threads, quota, router, tracer, chat)
