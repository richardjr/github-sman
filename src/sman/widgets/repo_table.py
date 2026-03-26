"""DataTable widget configured for repo listings."""

from __future__ import annotations

import humanize
from textual.widgets import DataTable

from sman.github.repos import RepoInfo


class RepoTable(DataTable):
    """A DataTable pre-configured for displaying repository listings."""

    def on_mount(self) -> None:
        self.cursor_type = "row"
        self.add_columns(
            "Name", "Language", "Stars", "Forks",
            "Issues", "Updated", "Visibility",
        )

    def populate(self, repos: list[RepoInfo]) -> None:
        """Clear and repopulate the table with repo data."""
        self.clear()
        for repo in repos:
            self.add_row(
                repo.name,
                repo.language or "-",
                str(repo.stars),
                str(repo.forks),
                str(repo.open_issues),
                humanize.naturaltime(repo.updated_at),
                "private" if repo.private else "public",
                key=repo.name,
            )
