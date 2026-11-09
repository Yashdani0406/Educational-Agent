"""The chat page: messages, agent labels, 'Ask instead' buttons and the input box."""

from fastapi.responses import RedirectResponse
from nicegui import ui

from eduagent.agents.routing import AGENT_NAMES, DISPLAY_NAMES, MENTIONS
from eduagent.chat.service import AgentReply
from eduagent.services import Services
from eduagent.ui.frame import UiState, page_frame
from eduagent.ui.mermaid import quote_mermaid_labels
from eduagent.ui.theme import MUTED, NOTICE_BG, PRIMARY

WHAT_IT_DOES = (
    "Shows a saved chat, sends what you type to the agents and labels each answer "
    "with the agent and model that wrote it."
)

_MD_EXTRAS = ["fenced-code-blocks", "tables", "mermaid"]


def _mention_for(agent: str) -> str:
    return next(tag for tag, a in MENTIONS.items() if a == agent)


class ChatView:
    def __init__(self, services: Services, thread_id: str, refresh_status) -> None:
        self.services, self.thread_id, self.refresh_status = services, thread_id, refresh_status
        self.busy = False

    def build(self, history: list[tuple[str, str]]) -> None:
        with ui.column().classes("w-full max-w-3xl mx-auto gap-3"):
            self.messages = ui.column().classes("w-full gap-3")
            with ui.row().classes("w-full items-end no-wrap"):
                self.box = ui.textarea(placeholder="Ask anything about your course").props(
                    "outlined autogrow rows=1"
                ).classes("grow")
                self.box.on("keydown.enter.exact.prevent", self.submit)
                self.send_button = ui.button("Send", on_click=self.submit)
        with self.messages:
            for author, text in history:
                if author == "user":
                    self._user_bubble(text)
                else:
                    name = DISPLAY_NAMES.get(author, author)  # type: ignore[call-overload]
                    self._reply(AgentReply(author, name, text, None, ""), None)

    def _user_bubble(self, text: str) -> None:
        with ui.row().classes("w-full justify-end"):
            ui.label(text).classes("q-pa-sm rounded-borders").style(
                f"background: {PRIMARY}; color: white; max-width: 80%; white-space: pre-wrap"
            )

    def _reply(self, reply: AgentReply, user_text: str | None) -> None:
        """`user_text` is None for replies reloaded from history: no caption, no buttons."""
        with ui.column().classes("gap-1 w-full"):
            with ui.row().classes("items-center gap-2"):
                ui.chip(reply.display_name).props("dense outline color=primary")
                if user_text is not None and reply.model:
                    ui.label(reply.model).classes("text-caption").style(f"color: {MUTED}")
            ui.markdown(quote_mermaid_labels(reply.text), extras=_MD_EXTRAS)
            if user_text is not None and reply.agent != "system":
                with ui.row().classes("items-center gap-1"):
                    ui.label("Ask instead:").classes("text-caption").style(f"color: {MUTED}")
                    for agent in AGENT_NAMES:
                        if agent != reply.agent:
                            ui.button(
                                DISPLAY_NAMES[agent],
                                on_click=lambda a=agent: self.ask_instead(user_text, reply, a),
                            ).props("flat dense no-caps size=sm").style(f"color: {MUTED}")

    async def submit(self) -> None:
        text = (self.box.value or "").strip()
        if text and not self.busy:
            self.box.value = ""
            await self._turn(text, text, lambda: self.services.chat.send(self.thread_id, text))

    async def ask_instead(self, user_text: str, wrong: AgentReply, agent) -> None:
        if self.busy:
            return
        shown = f"@{_mention_for(agent)} {user_text}"
        await self._turn(
            shown, user_text,
            lambda: self.services.chat.resend_to(self.thread_id, user_text, wrong, agent),
        )

    async def _turn(self, shown: str, original: str, run) -> None:
        self.busy = True
        self.box.disable()
        self.send_button.disable()
        with self.messages:
            self._user_bubble(shown)
            with ui.row().classes("items-center gap-2") as thinking:
                ui.spinner(size="sm")
                ui.label("Thinking…").style(f"color: {MUTED}")
        try:
            replies = await run()
        finally:
            thinking.delete()
            self.box.enable()
            self.send_button.enable()
            self.busy = False
        with self.messages:
            for reply in replies:
                self._reply(reply, original)
        self.refresh_status()


def _banner(warnings: list[str]) -> None:
    for message in list(warnings):
        row_classes = "w-full max-w-3xl mx-auto items-center no-wrap q-pa-sm rounded-borders"
        with ui.row().classes(row_classes).style(f"background: {NOTICE_BG}") as row:
            ui.label(message).classes("grow")
            ui.button(
                "Dismiss", on_click=lambda m=message, r=row: (warnings.remove(m), r.delete())
            ).props("flat dense no-caps")


def register(services: Services, state: UiState) -> None:
    @ui.page("/chat/{thread_id}")
    async def chat_page(thread_id: str):
        try:
            thread = services.threads.get(thread_id)
        except KeyError:
            return RedirectResponse("/")
        state.resolved = True
        state.course_id = thread.course_id
        history = await services.chat.history(thread_id)
        with page_frame(services, "Chat", state) as refresh:
            _banner(services.warnings)
            ChatView(services, thread_id, refresh).build(history)
