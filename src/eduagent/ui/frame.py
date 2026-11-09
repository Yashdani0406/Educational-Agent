"""The page frame: top bar, left drawer and the in-memory UI state."""

from contextlib import contextmanager
from dataclasses import dataclass

from nicegui import ui

from eduagent.services import Services
from eduagent.ui.theme import MUTED, SURFACE, mastery_color

WHAT_IT_DOES = (
    "Draws the top bar (model and Gemini quota), the course selector and map, "
    "the page links and the saved chats around every page."
)

LINKS = [
    ("Chat", "/"), ("Library", "/library"), ("Notes", "/notes"),
    ("Flashcards", "/flashcards"), ("Progress", "/progress"), ("How it works", "/how-it-works"),
]


@dataclass
class UiState:
    """What the UI remembers between pages (in memory only)."""

    course_id: int | None = None
    resolved: bool = False

    def ensure(self, services: Services) -> None:
        """First use: pick the course of the latest thread, else the first course, else none."""
        if self.resolved:
            return
        self.resolved = True
        courses = services.courses.list_courses()
        recent = [ts[0] for ts in (services.threads.list(c.id) for c in courses) if ts]
        if recent:
            self.course_id = max(recent, key=lambda t: t.updated_at).course_id
        elif courses:
            self.course_id = courses[0].id


def _status_texts(services: Services) -> tuple[str, str]:
    choice = services.router.choose("chat")
    model = f"Model: {choice.provider} · {choice.model_id}"
    if services.settings.effective_routing_mode == "all_qwen":
        return model, "Gemini: off (all Qwen)"
    return model, f"Gemini: {services.quota.remaining()} left today"


def _course_select(services: Services, state: UiState) -> ui.select:
    options = {c.id: c.name for c in services.courses.list_courses()}

    def changed(e) -> None:
        state.course_id = e.value
        ui.navigate.to("/")

    return ui.select(options, value=state.course_id, label="Course", on_change=changed).props(
        "dense outlined options-dense"
    ).classes("min-w-40")


def _new_course_dialog(services: Services, state: UiState) -> ui.dialog:
    with ui.dialog() as dialog, ui.card():
        name = ui.input("Course name").props("outlined dense autofocus").mark("course-name")

        def create() -> None:
            try:
                course = services.courses.create_course(name.value)
            except ValueError as e:
                ui.notify(str(e), type="negative")
                return
            state.course_id = course.id
            dialog.close()
            ui.navigate.to("/")

        name.on("keydown.enter", create)
        with ui.row():
            ui.button("Cancel", on_click=dialog.close).props("flat")
            ui.button("Create", on_click=create)
    return dialog


def _course_map(services: Services, state: UiState) -> None:
    if state.course_id is None:
        ui.label("No course yet").classes("text-caption").style(f"color: {MUTED}")
        return
    modules = services.courses.course_map(state.course_id)
    if not modules:
        ui.label("No modules yet").classes("text-caption").style(f"color: {MUTED}")
    for module in modules:
        with ui.expansion(module.name, value=True).props("dense").classes("w-full"):
            for topic in module.topics:
                with ui.row().classes("items-center gap-2 no-wrap"):
                    ui.icon("circle", size="10px").style(f"color: {mastery_color(topic.mastery)}")
                    ui.label(topic.name).classes("text-body2")


def _saved_chats(services: Services, state: UiState) -> None:
    async def new_chat() -> None:
        thread = await services.chat.new_thread(state.course_id)
        ui.navigate.to(f"/chat/{thread.id}")

    ui.label("Saved chats").classes("text-subtitle2").style(f"color: {MUTED}")
    ui.button("New chat", on_click=new_chat).props("flat dense no-caps")
    for thread in services.threads.list(state.course_id):
        ui.link(thread.title, f"/chat/{thread.id}").classes("text-body2 no-underline")


@contextmanager
def page_frame(services: Services, title: str, state: UiState):
    """Wrap a page. Yields a function that refreshes the top-bar model and quota."""
    state.ensure(services)
    ui.page_title(f"{title} · Educational Agent")
    with ui.header().classes("items-center gap-4 q-px-md").style(f"background: {SURFACE}; color: inherit"):
        ui.label("Educational Agent").classes("text-h6 text-primary")
        _course_select(services, state)
        ui.space()
        model_label = ui.label().classes("text-caption").style(f"color: {MUTED}")
        quota_label = ui.label().classes("text-caption").style(f"color: {MUTED}")

    def refresh() -> None:
        model_label.text, quota_label.text = _status_texts(services)

    refresh()
    ui.timer(30, refresh)

    with ui.left_drawer(fixed=True).props("bordered").classes("gap-2"):
        _course_select(services, state)
        dialog = _new_course_dialog(services, state)
        ui.button("New course", on_click=dialog.open).props("flat dense no-caps")
        ui.separator()
        _course_map(services, state)
        ui.separator()
        for label, href in LINKS:
            ui.link(label, href).classes("text-body1 no-underline")
        ui.separator()
        _saved_chats(services, state)

    yield refresh
