"""The coordinator: picks one agent per message and hands the conversation to it."""

import logging
from collections.abc import AsyncGenerator

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions

from eduagent.team.routing import Classifier, route
from eduagent.tracing.tracer import Tracer, current_trace_id

log = logging.getLogger(__name__)

WHAT_IT_DOES = (
    "Reads each chat message, decides which of the four agents should answer, "
    "records that choice, and lets that agent reply."
)


class CoordinatorAgent(BaseAgent):
    classify: Classifier
    tracer: Tracer

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        parts = ctx.user_content.parts if ctx.user_content and ctx.user_content.parts else []
        text = "\n".join(p.text for p in parts if p.text and not p.thought)
        last_agent = ctx.session.state.get("last_agent")
        decision = await route(text, last_agent, self.classify)
        log.info("routed to %s via %s", decision.agent, decision.method)
        log.debug("raw classifier label: %r", decision.raw_label)
        trace_id = current_trace_id.get()
        if trace_id:
            self.tracer.add_step(
                trace_id, "route", "coordinator",
                inputs={"last_agent": last_agent},
                outputs={
                    "agent": decision.agent,
                    "method": decision.method,
                    "raw_label": decision.raw_label,
                },
            )
        yield Event(
            author=self.name,
            invocation_id=ctx.invocation_id,
            actions=EventActions(state_delta={"last_agent": decision.agent}),
        )
        target = next(a for a in self.sub_agents if a.name == decision.agent)
        async for event in target.run_async(ctx):
            yield event
