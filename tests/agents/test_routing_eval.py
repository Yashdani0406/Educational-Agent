import pytest
from routing_cases import ROUTING_CASES

from eduagent.agents.routing import make_qwen_classifier, route
from eduagent.config import Settings

pytestmark = pytest.mark.ollama


async def test_routing_accuracy():
    classify = make_qwen_classifier(Settings())
    misses = []
    for message, last, want in ROUTING_CASES:
        got = (await route(message, last, classify)).agent
        if got != want:
            misses.append(f"{message} ({last}) -> {got}, want {want}")
    score = (len(ROUTING_CASES) - len(misses)) / len(ROUTING_CASES)
    print(f"\nrouting eval: {len(ROUTING_CASES) - len(misses)}/{len(ROUTING_CASES)}")
    for m in misses:
        print("MISS:", m)
    assert score >= 0.9
