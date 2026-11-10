from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from eduagent.team.coordinator import CoordinatorAgent
from eduagent.team.placeholder import PlaceholderAgent
from eduagent.team.routing import DISPLAY_NAMES
from eduagent.db.database import Database
from eduagent.tracing.tracer import Tracer, current_trace_id


def make(tmp_path, label):
    db = Database(tmp_path / "study.db")
    db.migrate()
    tracer = Tracer(db)

    async def classify(text, last_agent):
        return label

    agents = [PlaceholderAgent(name=n, display_name=d) for n, d in DISPLAY_NAMES.items()]
    coord = CoordinatorAgent(name="coordinator", sub_agents=agents, classify=classify, tracer=tracer)
    return coord, tracer


async def chat(coord, text):
    svc = InMemorySessionService()
    runner = Runner(app_name="t", agent=coord, session_service=svc)
    await svc.create_session(app_name="t", user_id="u", session_id="s")
    msg = types.Content(role="user", parts=[types.Part(text=text)])
    events = [e async for e in runner.run_async(user_id="u", session_id="s", new_message=msg)]
    return events, await svc.get_session(app_name="t", user_id="u", session_id="s")


async def test_routes_and_records(tmp_path):
    coord, tracer = make(tmp_path, "analytics")
    trace_id = tracer.start_trace("chat", "t")
    token = current_trace_id.set(trace_id)
    try:
        events, session = await chat(coord, "how am I doing?")
    finally:
        current_trace_id.reset(token)
    finals = [e for e in events if e.is_final_response()]
    assert finals[-1].author == "analytics"
    assert "isn't built yet" in finals[-1].content.parts[0].text
    assert session.state["last_agent"] == "analytics"
    step = next(s for s in tracer.get_trace(trace_id).steps if s.step_type == "route")
    assert step.outputs == {"agent": "analytics", "method": "classifier", "raw_label": "analytics"}


async def test_no_trace_still_works(tmp_path):
    coord, _ = make(tmp_path, "coding")
    events, session = await chat(coord, "@notes make notes")
    assert session.state["last_agent"] == "notes_maker"


async def test_attachment_routes_coding_in_coordinator(tmp_path):
    coord, tracer = make(tmp_path, "tutor")
    trace_id = tracer.start_trace("chat", "t")
    token = current_trace_id.set(trace_id)
    svc = InMemorySessionService()
    runner = Runner(app_name="t", agent=coord, session_service=svc)
    await svc.create_session(app_name="t", user_id="u", session_id="s")
    msg = types.Content(role="user", parts=[
        types.Part(text="look at this"),
        types.Part(inline_data=types.Blob(data=b"png-bytes", mime_type="image/png")),
    ])
    try:
        events = [e async for e in runner.run_async(user_id="u", session_id="s", new_message=msg)]
    finally:
        current_trace_id.reset(token)
    assert [e for e in events if e.is_final_response()][-1].author == "coding"
    step = next(s for s in tracer.get_trace(trace_id).steps if s.step_type == "route")
    assert step.outputs["agent"] == "coding" and step.outputs["method"] == "code"
