"""DataTable widget configured for repo listings."""

from __future__ import annotations

from pathlib import Path

import humanize
from rich.text import Text
from textual.widgets import DataTable

from sman.git_status import get_cached_local_status, status_char
from sman.github.persistent_cache import PersistentCache
from sman.github.repos import RepoInfo
from sman.local_repo import has_claude_md


class RepoTable(DataTable):
    """A DataTable pre-configured for displaying repository listings."""

    def on_mount(self) -> None:
        self.cursor_type = "row"
        self.add_columns(
            "S", "R", "Local", "Name", "Language", "Stars", "Forks",
            "Issues", "Updated", "Visibility",
        )

    def populate(
        self,
        repos: list[RepoInfo],
        work_dir: Path | None = None,
        persistent_cache: PersistentCache | None = None,
        excluded_repos: set[str] | None = None,
    ) -> None:
        """Clear and repopulate the table with repo data.

        ``persistent_cache`` is consulted (read-only) for a cached
        ``GitLocalStatus`` per repo, used to render the single-character
        status column. The list view never runs git itself — if no cache
        exists, the column shows "?" until the user opens the detail page.

        ``excluded_repos`` controls the "R" (report) column — repos in
        the set show blank, others show "✓".
        """
        self.clear()
        _excluded = excluded_repos or set()
        for repo in repos:
            local_path = work_dir / repo.name if work_dir is not None else None
            is_local = local_path is not None and local_path.is_dir()
            if is_local and has_claude_md(local_path):
                local_marker = "✓ C"
            elif is_local:
                local_marker = "✓"
            else:
                local_marker = ""

            if is_local and persistent_cache is not None:
                cached_status = get_cached_local_status(
                    persistent_cache, repo.name
                )
                char, colour = status_char(cached_status)
            else:
                # Not cloned locally: no meaningful status to show.
                char, colour = ("", "bright_black")
            status_cell = Text(char, style=colour)

            report_marker = "" if repo.name in _excluded else "✓"

            self.add_row(
                status_cell,
                report_marker,
                local_marker,
                repo.name,
                repo.language or "-",
                str(repo.stars),
                str(repo.forks),
                str(repo.open_issues),
                humanize.naturaltime(repo.updated_at),
                "private" if repo.private else "public",
                key=repo.full_name,
            )
