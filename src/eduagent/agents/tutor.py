"""The tutor agent: teaches concepts and checks understanding."""

from google.adk.agents import LlmAgent
from google.adk.models import BaseLlm

WHAT_IT_DOES = (
    "Explains concepts, answers doubts and checks understanding with one short "
    "question. For now it answers from general knowledge and says so."
)

TUTOR_INSTRUCTION = """You are a patient tutor for a data-science student.
- Teach the idea clearly, starting simple, with a small concrete example.
- Finish with one short question that checks understanding. Never nag or repeat yourself.
- There is no course material available yet. Label what you teach as "General knowledge (not from your material)".
- Use a Mermaid diagram in a ```mermaid code block when a picture helps."""


def build_tutor(model: BaseLlm) -> LlmAgent:
    return LlmAgent(
        name="tutor",
        model=model,
        description="Explains concepts, answers doubts, quizzes the student.",
        instruction=TUTOR_INSTRUCTION,
    )
