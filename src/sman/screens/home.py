"""Home screen — landing page with org summary and navigation."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Center, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Static


class HomeScreen(Screen):
    """Landing screen showing current org info and navigation."""

    BINDINGS = [
        ("r", "app.push_screen('repos')", "Repos"),
        ("d", "app.push_screen('reports')", "Reports"),
        ("s", "app.push_screen('settings')", "Settings"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="home-container"):
            yield Static("sman", id="home-title", classes="title")
            yield Static(
                "GitHub Simple Manager",
                id="home-subtitle",
                classes="subtitle",
            )
            yield Static("", id="home-org-info")
            with Center():
                yield Button("Repos [r]", id="btn-repos", variant="primary")
                yield Button("Reports [d]", id="btn-reports", variant="primary")
                yield Button("Settings [s]", id="btn-settings", variant="default")
        yield Footer()

    def on_mount(self) -> None:
        self._update_org_info()

    def on_screen_resume(self) -> None:
        self._update_org_info()

    def _update_org_info(self) -> None:
        info = self.query_one("#home-org-info", Static)
        app = self.app
        client = getattr(app, "current_client", None)
        if client:
            info.update(f"Connected to: {client.name} ({client.org_type})")
        else:
            info.update("No org configured — press [s] for settings")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        match event.button.id:
            case "btn-repos":
                self.app.push_screen("repos")
            case "btn-reports":
                self.app.push_screen("reports")
            case "btn-settings":
                self.app.push_screen("settings")
