"""Helpers for the local Qwen model served by Ollama."""

import logging
import re

import litellm

from eduagent.config import Settings

log = logging.getLogger(__name__)

WHAT_IT_DOES = (
    "Talks to the local Qwen model through Ollama and removes its 'thinking' "
    "text so answers are just the reply."
)

_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL)
_THINK_OPEN = re.compile(r"<think>.*", re.DOTALL)


def strip_think(text: str) -> str:
    """Remove <think> blocks (including an unclosed one) and trim."""
    text = _THINK_BLOCK.sub("", text)
    # Ollama with think=false can emit reasoning with only a closing tag.
    text = text.rsplit("</think>", 1)[-1]
    return _THINK_OPEN.sub("", text).strip()


def ollama_options(settings: Settings) -> dict[str, int]:
    """Extra litellm kwargs for Ollama; litellm puts unknown ones into Ollama's request `options`."""
    return {} if settings.ollama_use_gpu else {"num_gpu": 0}


async def qwen_complete(prompt: str, settings: Settings, *, system: str | None = None) -> str:
    messages = [{"role": "user", "content": prompt}]
    if system:
        messages.insert(0, {"role": "system", "content": system})
    log.debug("qwen_complete prompt=%r", prompt)
    response = await litellm.acompletion(
        model=f"ollama_chat/{settings.qwen_model}",
        messages=messages,
        api_base=settings.ollama_url,
        **ollama_options(settings),
    )
    return strip_think(response.choices[0].message.content or "")
