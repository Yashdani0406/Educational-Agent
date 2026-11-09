"""Calm 'coming later' pages for features that arrive in later plans."""

from nicegui import ui

from eduagent.services import Services
from eduagent.ui.frame import UiState, page_frame
from eduagent.ui.theme import MUTED

WHAT_IT_DOES = "Shows a quiet 'Coming in Plan N' card for pages that are not built yet."

PLACEHOLDERS = {
    "/library": ("Library", 2, "Your uploaded course material will live here."),
    "/notes": ("Notes", 3, "Generated revision notes will live here."),
    "/flashcards": ("Flashcards", 4, "Spaced-repetition review will live here."),
    "/progress": ("Progress", 5, "Mastery and score charts will live here."),
    "/how-it-works": ("How it works", 7, "A live map of the agents and models will live here."),
}


def register(services: Services, state: UiState) -> None:
    for route, (title, plan, blurb) in PLACEHOLDERS.items():

        def make(title=title, plan=plan, blurb=blurb):
            def page() -> None:
                with page_frame(services, title, state):
                    with ui.card().classes("max-w-md mx-auto mt-12"):
                        ui.label(title).classes("text-h6")
                        ui.label(f"Coming in Plan {plan}")
                        ui.label(blurb).style(f"color: {MUTED}")

            return page

        ui.page(route)(make())
