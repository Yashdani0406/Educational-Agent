"""Deep redaction of secrets from data before it is written to a trace."""

import re
from collections.abc import Sequence
from typing import Any

WHAT_IT_DOES = (
    "Strips API keys, tokens and other secrets from any data before it is written to a trace."
)

REDACTED = "[redacted]"

_SENSITIVE_KEY = re.compile(
    r"^(.*[_-])?(api[_-]?key|key|token|access[_-]?token|secret|password|authorization)$",
    re.IGNORECASE,
)


def scrub(text: str, secrets: Sequence[str]) -> str:
    """Replace every occurrence of each non-blank secret in text."""
    for s in secrets:
        if s and s.strip():
            text = text.replace(s, REDACTED)
    return text


def redact(value: Any, secrets: Sequence[str]) -> Any:
    """Return a deep copy with secret values scrubbed and sensitive keys masked."""
    if isinstance(value, str):
        return scrub(value, secrets)
    if isinstance(value, dict):
        return {
            k: REDACTED
            if isinstance(k, str) and _SENSITIVE_KEY.match(k)
            else redact(v, secrets)
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [redact(v, secrets) for v in value]
    if isinstance(value, tuple):
        return tuple(redact(v, secrets) for v in value)
    return value
