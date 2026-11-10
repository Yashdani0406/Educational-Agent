from google.adk.agents import BaseAgent
from google.adk.events import Event
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from eduagent.team.coordinator import CoordinatorAgent
from eduagent.team.placeholder import PlaceholderAgent
from eduagent.team.routing import DISPLAY_NAMES
from eduagent.chat.service import ChatService
from eduagent.config import Settings
from eduagent.db.database import Database
from eduagent.db.threads import ThreadsRepo
from eduagent.services import build_services
from eduagent.tracing.tracer import Tracer


class Boom(BaseAgent):
    async def _run_async_impl(self, ctx):
        raise RuntimeError("kaput")
        yield  # pragma: no cover


class Thinker(BaseAgent):
    async def _run_async_impl(self, ctx):
        yield Event(
            author=self.name,
            invocation_id=ctx.invocation_id,
            content=types.Content(
                role="model",
                parts=[types.Part(text="reasoning", thought=True), types.Part(text="answer")],
            ),
        )


def make(tmp_path, label, overrides=None):
    db = Database(tmp_path / "study.db")
    db.migrate()
    tracer = Tracer(db)
    threads = ThreadsRepo(db)

    async def classify(text, last_agent):
        return label

    agents = {n: PlaceholderAgent(name=n, display_name=d) for n, d in DISPLAY_NAMES.items()}
    agents.update(overrides or {})
    coord = CoordinatorAgent(
        name="coordinator", sub_agents=list(agents.values()), classify=classify, tracer=tracer
    )
    svc = InMemorySessionService()
    runner = Runner(app_name="eduagent", agent=coord, session_service=svc)
    return ChatService(runner, svc, threads, tracer), threads, tracer


async def test_send_returns_labelled_reply(tmp_path):
    chat, threads, tracer = make(tmp_path, "analytics")
    t = await chat.new_thread(None)
    replies = await chat.send(t.id, "how am I doing?")
    assert len(replies) == 1
    assert replies[0].display_name == "Analytics" and replies[0].agent == "analytics"
    assert replies[0].model is None
    trace = tracer.get_trace(replies[0].trace_id)
    assert trace.status == "ok"
    types_ = [s.step_type for s in trace.steps]
    assert "route" in types_ and types_.count("answer") == 1
    assert threads.get(t.id).last_agent == "analytics"


async def test_first_message_titles_thread(tmp_path):
    chat, threads, _ = make(tmp_path, "analytics")
    t = await chat.new_thread(None)
    await chat.send(t.id, "x" * 100)
    assert threads.get(t.id).title == "x" * 40
    await chat.send(t.id, "second message")
    assert threads.get(t.id).title == "x" * 40


async def test_agent_exception_returns_system_reply(tmp_path, caplog):
    chat, threads, tracer = make(tmp_path, "coding", {"coding": Boom(name="coding")})
    t = await chat.new_thread(None)
    replies = await chat.send(t.id, "fix my code")
    assert len(replies) == 1 and replies[0].agent == "system"
    assert replies[0].text == "Something went wrong: RuntimeError. Details are in the trace."
    trace = tracer.get_trace(replies[0].trace_id)
    assert trace.status == "error"
    err = next(s for s in trace.steps if s.step_type == "error")
    assert err.outputs == {"error": "RuntimeError", "message": "kaput"}
    assert threads.get(t.id).title == "New chat"
    assert "chat send failed" in caplog.text


async def test_history_roundtrip(tmp_path):
    chat, _, _ = make(tmp_path, "analytics")
    t = await chat.new_thread(None)
    await chat.send(t.id, "how am I doing?")
    h = await chat.history(t.id)
    assert [r for r, _ in h] == ["user", "analytics"]
    assert h[0][1] == "how am I doing?" and "isn't built yet" in h[1][1]


async def test_reply_excludes_thought_parts(tmp_path):
    chat, _, tracer = make(tmp_path, "tutor", {"tutor": Thinker(name="tutor")})
    t = await chat.new_thread(None)
    replies = await chat.send(t.id, "explain")
    assert [r.text for r in replies] == ["answer"]
    h = await chat.history(t.id)
    assert h[-1] == ("tutor", "answer")


async def test_resend_to_records_reroute(tmp_path):
    chat, _, tracer = make(tmp_path, "tutor")
    t = await chat.new_thread(None)
    [wrong] = await chat.send(t.id, "what is a dataframe?")
    [again] = await chat.resend_to(t.id, "what is a dataframe?", wrong, "coding")
    assert again.agent == "coding"
    steps = tracer.get_trace(again.trace_id).steps
    rr = next(s for s in steps if s.step_type == "reroute")
    assert rr.inputs["from_agent"] == "tutor" and rr.inputs["to_agent"] == "coding"
    assert rr.inputs["from_trace"] == wrong.trace_id
    route = next(s for s in steps if s.step_type == "route")
    assert route.outputs["method"] == "mention"


async def test_build_services_wires_real_session_store(tmp_path):
    services = build_services(Settings(_env_file=None, data_dir=tmp_path))
    t = await services.chat.new_thread(None)
    assert await services.chat.history(t.id) == []
