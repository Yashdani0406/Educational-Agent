"""Decides which agent answers a chat message: @mention, code, then a small Qwen classifier."""

import logging
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Literal

from eduagent.config import Settings
from eduagent.models.qwen import qwen_complete, strip_think

log = logging.getLogger(__name__)

WHAT_IT_DOES = (
    "Chooses which agent answers each message: an @mention wins, code goes to the "
    "coding agent, and anything else is classified by the local Qwen model, "
    "falling back to the previous agent or the tutor when unsure."
)

AgentName = Literal["tutor", "notes_maker", "coding", "analytics"]
MENTIONS: dict[str, AgentName] = {
    "tutor": "tutor", "notes": "notes_maker", "code": "coding", "progress": "analytics",
}
DISPLAY_NAMES: dict[AgentName, str] = {
    "tutor": "Tutor", "notes_maker": "Notes maker", "coding": "Coding", "analytics": "Analytics",
}
AGENT_NAMES: tuple[AgentName, ...] = tuple(DISPLAY_NAMES)

Classifier = Callable[[str, AgentName | None], Awaitable[str]]

_MENTION = re.compile(r"^\s*@(\w+)(?:\s+(.*))?$", re.DOTALL)

ROUTER_PROMPT = """You are the router of a study app for a data-science student. Pick the ONE agent that should answer.

Agents:
- tutor: explains concepts and theory, answers doubts, maths, "why/how does X work", runs quizzes and flashcard reviews, explains simpler.
- notes_maker: ONLY when the student asks to CREATE notes, summaries, revision sheets or flashcards for a module/topic.
- coding: anything about specific code or programming: what code does, errors, tracebacks, bugs, library/function usage (pandas, numpy, sklearn, Python syntax), how to write or fix code.
- analytics: the student's OWN performance: progress, scores, mastery, weak/strong topics, quiz history, "how am I doing".

Rules:
- Each message starts with "Previous agent: <name or none>". Short follow-ups ("why?", "more", "another example", "I don't get it") stay with the previous agent.
- Explaining a concept is tutor, even if it is a coding-related concept like recursion or Big-O, unless the student is asking about specific code or a library call.
- If unsure, answer tutor.

Examples:
"what is overfitting?" -> tutor
"make flashcards for module 2" -> notes_maker
"why does my loop never end?" -> coding
"what does df.groupby return?" -> coding
"I got a KeyError when indexing my dataframe" -> coding
"am I getting better at statistics?" -> analytics
"give me a quick summary sheet of PCA to revise" -> notes_maker
"test me on regression" -> tutor
(previous agent: coding) "show me another one" -> coding
(previous agent: tutor) "why?" -> tutor
(previous agent: analytics) "and last month?" -> analytics

Reply with exactly one word: tutor, notes_maker, coding or analytics."""


def parse_mention(text: str) -> tuple[AgentName | None, str]:
    """Only a leading @mention counts. Unknown tags are left in the text."""
    m = _MENTION.match(text)
    agent = MENTIONS.get(m.group(1).lower()) if m else None
    if m is None or agent is None:
        return None, text
    return agent, (m.group(2) or "").strip()


@dataclass(frozen=True)
class RouteDecision:
    agent: AgentName
    method: Literal["mention", "code", "classifier", "default"]
    raw_label: str | None = None


def classifier_message(text: str, last_agent: AgentName | None) -> str:
    return f"Previous agent: {last_agent or 'none'}\nStudent message: {text}"


def make_qwen_classifier(settings: Settings) -> Classifier:
    async def classify(text: str, last_agent: AgentName | None) -> str:
        return await qwen_complete(
            classifier_message(text, last_agent), settings, system=ROUTER_PROMPT
        )

    return classify


async def route(
    text: str,
    last_agent: AgentName | None,
    classify: Classifier,
    *,
    has_attachment: bool = False,
) -> RouteDecision:
    mentioned, _ = parse_mention(text)
    if mentioned:
        return RouteDecision(mentioned, "mention")
    if "```" in text or has_attachment:
        return RouteDecision("coding", "code")
    fallback = RouteDecision(last_agent or "tutor", "default")
    try:
        raw = strip_think(await classify(text, last_agent))
    except Exception:
        log.warning("Routing classifier failed; using default agent", exc_info=True)
        return fallback
    positions = {a: raw.lower().find(a) for a in AGENT_NAMES}
    hits = {a: i for a, i in positions.items() if i >= 0}
    found = min(hits, key=hits.get) if hits else None
    log.debug("classifier raw label %r for message %r", raw, text)
    if found is None:
        return RouteDecision(fallback.agent, "default", raw)
    return RouteDecision(found, "classifier", raw)
