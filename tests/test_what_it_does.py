import importlib

import pytest

MODULES = [
    "config", "logging_setup", "launcher", "services",
    "db.database", "db.courses", "db.threads",
    "tracing.redact", "tracing.tracer",
    "models.quota", "models.qwen", "models.router", "models.routed_llm",
    "team.coordinator", "team.placeholder", "team.registry", "team.routing", "team.tutor",
    "chat.service",
    "ui.app", "ui.frame", "ui.mermaid", "ui.theme", "ui.pages.chat", "ui.pages.placeholders",
]


@pytest.mark.parametrize("name", MODULES)
def test_module_says_what_it_does(name):
    text = importlib.import_module(f"eduagent.{name}").WHAT_IT_DOES
    assert isinstance(text, str) and text.strip()
