"""Help screen showing all keyboard shortcuts."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Static

HELP_TEXT = """\
[bold]Keyboard Shortcuts[/bold]


 [bold underline]Global[/bold underline]

   [bold]h[/bold]            Help (this screen)
   [bold]o[/bold]            Switch Org
   [bold]Esc[/bold]          Back / Close
   [bold]q[/bold]            Quit

 [bold underline]Home[/bold underline]

   [bold]r[/bold]            Repos
   [bold]d[/bold]            Reports
   [bold]s[/bold]            Settings

 [bold underline]Repositories[/bold underline]

   [bold]c[/bold]            Create Repo
   [bold]Ctrl+R[/bold]       Refresh
   [bold]Enter[/bold]        View Details

 [bold underline]Repo Detail[/bold underline]

   [bold]g[/bold]            Clone repo (git clone)

 [bold underline]Reports[/bold underline]

   [bold]Ctrl+R[/bold]       Refresh

 [bold underline]Tables[/bold underline]

   [bold]↑ ↓[/bold]          Navigate rows
   [bold]Enter[/bold]        Select row
"""


class HelpScreen(ModalScreen):
    """Modal showing all keyboard shortcuts."""

    BINDINGS = [
        Binding("h", "close_help", "Close", show=False),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="help-container"):
            with VerticalScroll():
                yield Static(HELP_TEXT, id="help-text")
            yield Static(
                " Press [bold]Esc[/bold] or [bold]h[/bold] to close ",
                id="help-close-hint",
            )

    def action_close_help(self) -> None:
        self.dismiss()
