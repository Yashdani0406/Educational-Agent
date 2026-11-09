"""One calm colour scheme and one sans font for the whole app."""

from nicegui import app, ui

WHAT_IT_DOES = "Sets the app's single colour palette and system font so every page looks the same."

PRIMARY = "#35618C"
BACKGROUND = "#F7F8FA"
SURFACE = "#FFFFFF"
TEXT = "#1F2933"
MUTED = "#6B7785"
MASTERY = {"strong": "#3A8D5C", "okay": "#C9A227", "weak": "#C0504D", "untested": "#9AA5B1"}

_FONT = 'system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif'


def mastery_color(mastery: float | None) -> str:
    """Dot colour for a topic: grey until it has been tested."""
    if mastery is None:
        return MASTERY["untested"]
    if mastery >= 0.75:
        return MASTERY["strong"]
    if mastery >= 0.4:
        return MASTERY["okay"]
    return MASTERY["weak"]


def apply_theme() -> None:
    """Call once at start-up, before `ui.run`."""
    app.colors(primary=PRIMARY, secondary=MUTED, muted=MUTED)
    ui.add_css(
        f"body {{ background: {BACKGROUND}; color: {TEXT}; font-family: {_FONT}; }}"
        f" .q-drawer {{ background: {SURFACE}; }}"
        f" .text-muted {{ color: {MUTED}; }}",
        shared=True,
    )
