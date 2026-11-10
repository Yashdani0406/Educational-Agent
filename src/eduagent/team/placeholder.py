"""Stand-in for an agent that is not built yet."""

from collections.abc import AsyncGenerator

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.genai import types

WHAT_IT_DOES = (
    "Answers with a short 'not built yet' message for an agent that a later plan "
    "will add. It never calls a model."
)

PLAN_FOR = {"notes_maker": 3, "coding": 6, "analytics": 5}


class PlaceholderAgent(BaseAgent):
    display_name: str
    plan: int | None = None

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        plan = self.plan or PLAN_FOR.get(self.name)
        when = f"coming in Plan {plan}" if plan else "coming in a later plan"
        text = f"{self.display_name} isn't built yet — {when}."
        yield Event(
            author=self.name,
            invocation_id=ctx.invocation_id,
            content=types.Content(role="model", parts=[types.Part(text=text)]),
        )
