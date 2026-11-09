"""One-command start-up: checks the setup, builds the services and runs the web UI."""

import logging
from collections.abc import Callable

import httpx
from nicegui import ui

from eduagent.config import Settings
from eduagent.logging_setup import configure_logging
from eduagent.services import build_services
from eduagent.ui.app import apply_theme, register_pages

log = logging.getLogger(__name__)

WHAT_IT_DOES = "Starts the app with one command and warns about anything missing, such as Ollama or a model."


def _has_model(wanted: str, available: list[str]) -> bool:
    """A name without a tag means `:latest`, so `X` matches `X` and `X:latest`."""
    return wanted in available or f"{wanted}:latest" in available


def preflight(settings: Settings, fetch_ollama_models: Callable[[], list[str]]) -> list[str]:
    """Return human-readable warnings; an empty list means everything is ready."""
    warnings = []
    key = settings.gemini_api_key
    if key is None or not key.get_secret_value().strip():
        warnings.append("No GEMINI_API_KEY in .env — running everything on Qwen.")
    try:
        available = fetch_ollama_models()
    except httpx.HTTPError:
        warnings.append("Ollama isn't running. Start it with: ollama serve")
        return warnings
    for name in (settings.qwen_model, settings.embed_model):
        if not _has_model(name, available):
            warnings.append(f"Model {name} not found. Run: ollama pull {name}")
    return warnings


def main() -> None:
    settings = Settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    configure_logging(settings)  # first, so start-up is logged
    log.info("Starting Educational Agent (routing mode: %s)", settings.effective_routing_mode)

    def fetch_models() -> list[str]:
        response = httpx.get(f"{settings.ollama_url}/api/tags", timeout=3)
        response.raise_for_status()
        return [m["name"] for m in response.json().get("models", [])]

    warnings = preflight(settings, fetch_models)
    for warning in warnings:
        log.warning(warning)
    services = build_services(settings)  # also creates and migrates the database
    services.warnings.extend(warnings)
    apply_theme()
    register_pages(services)
    ui.run(host="127.0.0.1", port=8000, title="Educational Agent", reload=False, show=True)
