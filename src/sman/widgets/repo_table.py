"""DataTable widget configured for repo listings."""

from __future__ import annotations

from pathlib import Path

import humanize
from textual.widgets import DataTable

from sman.github.repos import RepoInfo


class RepoTable(DataTable):
    """A DataTable pre-configured for displaying repository listings."""

    def on_mount(self) -> None:
        self.cursor_type = "row"
        self.add_columns(
            "Local", "Name", "Language", "Stars", "Forks",
            "Issues", "Updated", "Visibility",
        )

    def populate(
        self, repos: list[RepoInfo], work_dir: Path | None = None
    ) -> None:
        """Clear and repopulate the table with repo data."""
        self.clear()
        for repo in repos:
            is_local = (
                work_dir is not None and (work_dir / repo.name).is_dir()
            )
            self.add_row(
                "✓" if is_local else "",
                repo.name,
                repo.language or "-",
                str(repo.stars),
                str(repo.forks),
                str(repo.open_issues),
                humanize.naturaltime(repo.updated_at),
                "private" if repo.private else "public",
                key=repo.full_name,
            )
