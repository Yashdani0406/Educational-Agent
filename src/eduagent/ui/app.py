"""Defines every page route of the app."""

from fastapi.responses import RedirectResponse
from nicegui import ui

from eduagent.services import Services
from eduagent.ui.frame import UiState
from eduagent.ui.pages import chat, placeholders
from eduagent.ui.theme import apply_theme

__all__ = ["apply_theme", "register_pages"]

WHAT_IT_DOES = "Registers the chat page, the placeholder pages and the home redirect."


def register_pages(services: Services) -> None:
    state = UiState()

    @ui.page("/")
    async def home():
        state.ensure(services)
        threads = services.threads.list(state.course_id)
        thread = threads[0] if threads else await services.chat.new_thread(state.course_id)
        return RedirectResponse(f"/chat/{thread.id}")

    chat.register(services, state)
    placeholders.register(services, state)
