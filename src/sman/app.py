"""Textual app for github-sman."""

from __future__ import annotations

from pathlib import Path

from textual.app import App, ComposeResult
from textual.widgets import Footer, Header

from sman.config import Config
from sman.github.client import GitHubClient
from sman.screens.home import HomeScreen
from sman.widgets.org_switcher import OrgSwitcher


class SmanApp(App):
    """GitHub simple management TUI."""

    TITLE = "sman"
    SUB_TITLE = "GitHub Simple Manager"
    CSS_PATH = Path("styles/app.tcss")

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("o", "switch_org", "Switch Org"),
        ("escape", "pop_screen", "Back"),
    ]

    SCREENS = {
        "home": HomeScreen,
    }

    def __init__(self) -> None:
        super().__init__()
        self.config = Config.load()
        self._clients: dict[str, GitHubClient] = {}
        self.current_client: GitHubClient | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        org_names = [o.name for o in self.config.orgs]
        current = self.config.default_org
        yield OrgSwitcher(org_names, current)
        yield Footer()

    def on_mount(self) -> None:
        # Lazy-import screens to avoid circular imports and register them
        from sman.screens.reports import ReportsScreen
        from sman.screens.repos import RepoListScreen
        from sman.screens.settings import SettingsScreen

        self.install_screen(RepoListScreen, name="repos")
        self.install_screen(ReportsScreen, name="reports")
        self.install_screen(SettingsScreen, name="settings")

        # Connect to default org if configured
        default_org = self.config.get_default_org()
        if default_org:
            self._connect_org(default_org.name)

        self.push_screen("home")

    def _connect_org(self, org_name: str) -> bool:
        """Connect to an org, reusing cached client if available."""
        if org_name in self._clients:
            self.current_client = self._clients[org_name]
            return True

        org_config = self.config.get_org(org_name)
        if not org_config or not org_config.resolve_token():
            self.notify(f"No token for '{org_name}'", severity="error")
            return False

        try:
            client = GitHubClient.from_config(
                org_config, cache_ttl=self.config.cache_ttl_seconds
            )
            self._clients[org_name] = client
            self.current_client = client
            self.notify(f"Connected to {org_name}")
            return True
        except Exception as e:
            self.notify(f"Failed to connect: {e}", severity="error")
            return False

    def on_org_switcher_org_changed(self, event: OrgSwitcher.OrgChanged) -> None:
        self._connect_org(event.org_name)

    def action_switch_org(self) -> None:
        """Focus the org switcher dropdown."""
        try:
            switcher = self.query_one(OrgSwitcher)
            switcher.query_one("#org-select").focus()
        except Exception:
            pass

    def action_pop_screen(self) -> None:
        """Pop screen if not at the base."""
        if len(self.screen_stack) > 2:  # App base + home
            self.pop_screen()
