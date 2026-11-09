"""Runs a chat message through the agents, records every step, and keeps threads."""

import logging
from dataclasses import dataclass

from google.adk.events import Event
from google.adk.runners import Runner
from google.adk.sessions import BaseSessionService
from google.genai import types

from eduagent.agents.routing import DISPLAY_NAMES, MENTIONS, AgentName
from eduagent.db.threads import Thread, ThreadsRepo
from eduagent.tracing.tracer import Tracer, current_trace_id

log = logging.getLogger(__name__)

WHAT_IT_DOES = (
    "Sends each chat message to the agents, records how the answer was produced, "
    "and keeps saved chats so you can reopen them."
)

USER_ID = "student"
DEFAULT_TITLE = "New chat"


@dataclass(frozen=True)
class AgentReply:
    agent: str
    display_name: str
    text: str
    model: str | None
    trace_id: str


def _text(content: types.Content | None) -> str:
    parts = content.parts if content and content.parts else []
    return "".join(p.text for p in parts if p.text and not p.thought)


class ChatService:
    def __init__(
        self,
        runner: Runner,
        session_service: BaseSessionService,
        threads: ThreadsRepo,
        tracer: Tracer,
        app_name: str = "eduagent",
    ) -> None:
        self._runner = runner
        self._sessions = session_service
        self._threads = threads
        self._tracer = tracer
        self._app = app_name

    async def new_thread(self, course_id: int | None) -> Thread:
        thread = self._threads.create(course_id)
        await self._sessions.create_session(
            app_name=self._app, user_id=USER_ID, session_id=thread.id
        )
        return thread

    async def send(self, thread_id: str, text: str) -> list[AgentReply]:
        return await self._run(thread_id, text)

    async def resend_to(
        self, thread_id: str, user_text: str, wrong: AgentReply, agent: AgentName
    ) -> list[AgentReply]:
        tag = next(t for t, a in MENTIONS.items() if a == agent)
        log.info("reroute %s -> %s", wrong.agent, agent)
        return await self._run(
            thread_id,
            f"@{tag} {user_text}",
            reroute={
                "from_trace": wrong.trace_id,
                "from_agent": wrong.agent,
                "to_agent": agent,
                "text": user_text,
            },
        )

    async def _run(
        self, thread_id: str, text: str, reroute: dict | None = None
    ) -> list[AgentReply]:
        trace_id = self._tracer.start_trace("chat", text[:60])
        token = current_trace_id.set(trace_id)
        try:
            if reroute:
                self._tracer.add_step(trace_id, "reroute", "chat", inputs=reroute)
            finals: list[tuple[str, str]] = []
            message = types.Content(role="user", parts=[types.Part(text=text)])
            async for event in self._runner.run_async(
                user_id=USER_ID, session_id=thread_id, new_message=message
            ):
                self._record(trace_id, event, finals)
            steps = self._tracer.get_trace(trace_id).steps
            model = next((s.model for s in reversed(steps) if s.step_type == "model_call"), None)
            replies = [
                AgentReply(a, DISPLAY_NAMES.get(a, a), t, model, trace_id)  # type: ignore[call-overload]
                for a, t in finals
            ]
            if replies:
                self._threads.touch(thread_id, replies[-1].agent)
            if self._threads.get(thread_id).title == DEFAULT_TITLE:
                self._threads.rename(thread_id, text[:40])
            self._tracer.end_trace(trace_id, "ok")
            return replies
        except Exception as exc:
            log.exception("chat send failed")
            self._tracer.add_step(
                trace_id, "error", "chat",
                outputs={"error": type(exc).__name__, "message": str(exc)},
            )
            self._tracer.end_trace(trace_id, "error")
            return [
                AgentReply(
                    "system", "System",
                    f"Something went wrong: {type(exc).__name__}. Details are in the trace.",
                    None, trace_id,
                )
            ]
        finally:
            current_trace_id.reset(token)

    def _record(self, trace_id: str, event: Event, finals: list[tuple[str, str]]) -> None:
        for call in event.get_function_calls():
            self._tracer.add_step(
                trace_id, "tool_call", event.author,
                inputs={"name": call.name, "args": call.args},
            )
        for resp in event.get_function_responses():
            self._tracer.add_step(
                trace_id, "tool_result", event.author,
                outputs={"name": resp.name, "response": resp.response},
            )
        text = _text(event.content)
        if event.is_final_response() and text:
            self._tracer.add_step(trace_id, "answer", event.author, outputs={"text": text})
            finals.append((event.author, text))

    async def history(self, thread_id: str) -> list[tuple[str, str]]:
        session = await self._sessions.get_session(
            app_name=self._app, user_id=USER_ID, session_id=thread_id
        )
        if session is None:
            return []
        return [(e.author, t) for e in session.events if (t := _text(e.content))]
