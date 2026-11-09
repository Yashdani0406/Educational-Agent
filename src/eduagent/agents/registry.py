"""Wires the four agents and the coordinator together."""

from eduagent.agents.coordinator import CoordinatorAgent
from eduagent.agents.placeholder import PlaceholderAgent
from eduagent.agents.routing import DISPLAY_NAMES, AgentName, Classifier, make_qwen_classifier
from eduagent.agents.tutor import build_tutor
from eduagent.config import Settings
from eduagent.models.quota import QuotaTracker
from eduagent.models.routed_llm import build_routed_llm
from eduagent.models.router import ModelRouter
from eduagent.tracing.tracer import Tracer

WHAT_IT_DOES = (
    "Builds the coordinator with the tutor and the placeholder agents that later "
    "plans will replace."
)


def build_coordinator(
    settings: Settings,
    router: ModelRouter,
    quota: QuotaTracker,
    tracer: Tracer,
    classify: Classifier | None = None,
) -> CoordinatorAgent:
    tutor = build_tutor(build_routed_llm("chat", settings, router, quota, tracer))
    others: list[AgentName] = ["notes_maker", "coding", "analytics"]
    return CoordinatorAgent(
        name="coordinator",
        sub_agents=[tutor, *(PlaceholderAgent(name=n, display_name=DISPLAY_NAMES[n]) for n in others)],
        classify=classify or make_qwen_classifier(settings),
        tracer=tracer,
    )
