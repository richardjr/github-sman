"""Org switcher widget for selecting the active GitHub org/account."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.message import Message
from textual.widgets import Select, Static


class OrgSwitcher(Static):
    """Dropdown for switching between configured GitHub orgs."""

    class OrgChanged(Message):
        """Posted when the user selects a different org."""

        def __init__(self, org_name: str) -> None:
            super().__init__()
            self.org_name = org_name

    def __init__(self, org_names: list[str], current: str = "") -> None:
        super().__init__()
        self._org_names = org_names
        self._current = current

    def compose(self) -> ComposeResult:
        options = [(name, name) for name in self._org_names]
        yield Select(
            options,
            value=self._current or (
                self._org_names[0] if self._org_names else Select.BLANK
            ),
            prompt="Select org",
            id="org-select",
        )

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.value and event.value != Select.BLANK:
            self.post_message(self.OrgChanged(str(event.value)))

    def update_orgs(self, org_names: list[str], current: str = "") -> None:
        """Update the available orgs and current selection."""
        self._org_names = org_names
        self._current = current
        select = self.query_one("#org-select", Select)
        select.set_options([(name, name) for name in org_names])
        if current:
            select.value = current
