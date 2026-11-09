"""Application logging: rotating file, console on stderr, trace ids, secret scrubbing."""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from eduagent.config import Settings
from eduagent.tracing import current_trace_id
from eduagent.tracing.redact import scrub

WHAT_IT_DOES = (
    "Sets up logging to a rotating file and the console, tags each line with the current trace id, and scrubs secrets before anything is written."
)

LOG_FORMAT = "%(asctime)s %(levelname)-7s [%(name)s] trace=%(trace_id)s %(message)s"
NOISY_LIBRARIES = ("litellm", "LiteLLM", "httpx", "httpcore", "google_genai", "urllib3", "watchfiles")


class TraceIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.trace_id = current_trace_id.get() or "-"
        return True


class RedactingFormatter(logging.Formatter):
    def __init__(self, fmt: str | None = None, secrets: list[str] | None = None):
        super().__init__(fmt)
        self._secrets = [s for s in (secrets or []) if s and s.strip()]

    def format(self, record: logging.LogRecord) -> str:
        return scrub(super().format(record), self._secrets)


def configure_logging(settings: Settings) -> Path:
    """Set up root logging; safe to call repeatedly. Returns the log file path."""
    key = settings.gemini_api_key.get_secret_value() if settings.gemini_api_key else ""
    formatter = RedactingFormatter(LOG_FORMAT, [key])
    settings.log_dir.mkdir(parents=True, exist_ok=True)
    path = settings.log_dir / "eduagent.log"

    file_handler = RotatingFileHandler(
        path, maxBytes=5_000_000, backupCount=5, encoding="utf-8"
    )
    file_level = logging.getLevelName(settings.log_level)
    file_handler.setLevel(file_level)
    console = logging.StreamHandler(sys.stderr)
    console.setLevel(logging.INFO)

    root = logging.getLogger()
    for old in [h for h in root.handlers if getattr(h, "_eduagent", False)]:
        root.removeHandler(old)
        old.close()
    for h in (file_handler, console):
        h._eduagent = True  # type: ignore[attr-defined]
        h.addFilter(TraceIdFilter())
        h.setFormatter(formatter)
        root.addHandler(h)
    root.setLevel(min(file_level, logging.INFO))

    for name in NOISY_LIBRARIES:
        logging.getLogger(name).setLevel(logging.WARNING)
    return path
