"""Date range input widget with presets."""

from __future__ import annotations

from datetime import datetime, timedelta

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.message import Message
from textual.widgets import Button, Input, Select, Static


class DateRange(Static):
    """Date range picker with from/to inputs and preset shortcuts."""

    class DateRangeChanged(Message):
        """Posted when the date range changes."""

        def __init__(self, since: datetime, until: datetime) -> None:
            super().__init__()
            self.since = since
            self.until = until

    def compose(self) -> ComposeResult:
        today = datetime.now()
        week_ago = today - timedelta(days=7)

        with Horizontal(id="date-range-bar"):
            yield Input(
                value=week_ago.strftime("%Y-%m-%d"),
                placeholder="YYYY-MM-DD",
                id="date-from",
            )
            yield Input(
                value=today.strftime("%Y-%m-%d"),
                placeholder="YYYY-MM-DD",
                id="date-to",
            )
            yield Select(
                [
                    ("Last 7 days", "7"),
                    ("Last 30 days", "30"),
                    ("Last 90 days", "90"),
                ],
                value="7",
                id="date-preset",
            )
            yield Button("Go", variant="primary", id="btn-go")

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id != "date-preset":
            return
        if event.value and event.value != Select.BLANK:
            days = int(event.value)
            today = datetime.now()
            since = today - timedelta(days=days)
            self.query_one("#date-from", Input).value = since.strftime("%Y-%m-%d")
            self.query_one("#date-to", Input).value = today.strftime("%Y-%m-%d")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-go":
            self._emit_range()

    def _emit_range(self) -> None:
        try:
            since = datetime.strptime(
                self.query_one("#date-from", Input).value.strip(), "%Y-%m-%d"
            )
            until = datetime.strptime(
                self.query_one("#date-to", Input).value.strip(), "%Y-%m-%d"
            )
            # Set until to end of day
            until = until.replace(hour=23, minute=59, second=59)
            self.post_message(self.DateRangeChanged(since, until))
        except ValueError:
            self.app.notify("Invalid date format — use YYYY-MM-DD", severity="error")

    def get_range(self) -> tuple[datetime, datetime]:
        """Return the current date range."""
        since = datetime.strptime(
            self.query_one("#date-from", Input).value.strip(), "%Y-%m-%d"
        )
        until = datetime.strptime(
            self.query_one("#date-to", Input).value.strip(), "%Y-%m-%d"
        )
        until = until.replace(hour=23, minute=59, second=59)
        return since, until
