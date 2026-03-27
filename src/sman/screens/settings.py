"""Settings screen — org/token CRUD."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, Checkbox, DataTable, Footer, Input, Label, Static

from sman.config import OrgConfig


class SettingsScreen(Screen):
    """Manage configured GitHub orgs and tokens."""

    def compose(self) -> ComposeResult:
        with Vertical(id="settings-container"):
            yield Static("Settings", classes="title")
            yield Static("General", classes="subtitle")
            with Vertical(id="general-form"):
                yield Label("Work directory (for cloning repos)")
                yield Input(placeholder="~/Work", id="work-dir")
            yield Button("Save General", variant="success", id="btn-save-general")
            yield Static("")
            yield Static("GitHub Orgs", classes="subtitle")
            yield DataTable(id="org-table")
            yield Static("")
            yield Static("Add / Edit Org", classes="subtitle")
            with Vertical(id="org-form"):
                yield Label("Org/Account name")
                yield Input(placeholder="my-org", id="org-name")
                yield Label("Token (or leave blank to use env var)")
                yield Input(placeholder="ghp_...", password=True, id="org-token")
                yield Label("Env var name (alternative to token)")
                yield Input(placeholder="SMAN_MY_ORG_TOKEN", id="org-token-env")
                yield Checkbox("Personal account (not org)", id="org-is-user")
                yield Checkbox("Set as default", value=True, id="org-is-default")
            yield Button("Save Org", variant="success", id="btn-save-org")
            yield Button("Delete Selected", variant="error", id="btn-delete-org")
            yield Static("", id="settings-status")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#work-dir", Input).value = self.app.config.work_dir
        table = self.query_one("#org-table", DataTable)
        table.cursor_type = "row"
        table.add_columns("Name", "Type", "Token Source", "Default")
        self._refresh_table()

    def on_screen_resume(self) -> None:
        self._refresh_table()

    def _refresh_table(self) -> None:
        table = self.query_one("#org-table", DataTable)
        table.clear()
        config = self.app.config
        for org in config.orgs:
            source = "env:" + org.token_env if org.token_env else "token"
            is_default = "yes" if org.name == config.default_org else ""
            table.add_row(org.name, org.type, source, is_default, key=org.name)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-save-general":
            self._save_general()
        elif event.button.id == "btn-save-org":
            self._save_org()
        elif event.button.id == "btn-delete-org":
            self._delete_org()

    def _save_general(self) -> None:
        work_dir = self.query_one("#work-dir", Input).value.strip()
        config = self.app.config
        config.work_dir = work_dir
        config.save()
        self.query_one("#settings-status", Static).update(
            "[green]General settings saved[/green]"
        )

    def _save_org(self) -> None:
        name = self.query_one("#org-name", Input).value.strip()
        if not name:
            status = self.query_one("#settings-status", Static)
            status.update("[red]Name is required[/red]")
            return

        token = self.query_one("#org-token", Input).value.strip()
        token_env = self.query_one("#org-token-env", Input).value.strip()
        is_user = self.query_one("#org-is-user", Checkbox).value
        is_default = self.query_one("#org-is-default", Checkbox).value

        if not token and not token_env:
            self.query_one("#settings-status", Static).update(
                "[red]Provide either a token or env var name[/red]"
            )
            return

        org = OrgConfig(
            name=name,
            token=token,
            token_env=token_env,
            type="user" if is_user else "org",
        )
        config = self.app.config
        config.add_org(org)
        if is_default:
            config.default_org = name
        config.save()

        # Update the org switcher
        from sman.widgets.org_switcher import OrgSwitcher

        try:
            switcher = self.app.query_one(OrgSwitcher)
            switcher.update_orgs(
                [o.name for o in config.orgs], config.default_org
            )
        except Exception:
            pass

        self._refresh_table()
        self._clear_form()
        self.query_one("#settings-status", Static).update(
            f"[green]Saved '{name}'[/green]"
        )

    def _delete_org(self) -> None:
        table = self.query_one("#org-table", DataTable)
        row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
        if not row_key or not row_key.value:
            return

        name = row_key.value
        config = self.app.config
        if config.remove_org(name):
            config.save()
            self._refresh_table()
            self.query_one("#settings-status", Static).update(
                f"[yellow]Removed '{name}'[/yellow]"
            )
        else:
            self.query_one("#settings-status", Static).update(
                f"[red]Org '{name}' not found[/red]"
            )

    def _clear_form(self) -> None:
        self.query_one("#org-name", Input).value = ""
        self.query_one("#org-token", Input).value = ""
        self.query_one("#org-token-env", Input).value = ""
        self.query_one("#org-is-user", Checkbox).value = False
        self.query_one("#org-is-default", Checkbox).value = True
