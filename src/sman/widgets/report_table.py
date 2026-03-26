"""DataTable widget configured for report data."""

from __future__ import annotations

import humanize
from textual.widgets import DataTable

from sman.github.activity import CommitActivity, PullRequestActivity, ReviewActivity
from sman.github.issues import IssueActivity
from sman.github.stats import OrgRepoSummary


class CommitTable(DataTable):
    """Table for commit activity."""

    def on_mount(self) -> None:
        self.cursor_type = "row"
        self.add_columns("Author", "Repo", "SHA", "Message", "Date", "+/-")

    def populate(self, commits: list[CommitActivity]) -> None:
        self.clear()
        for c in commits:
            self.add_row(
                c.author,
                c.repo,
                c.sha,
                c.message,
                humanize.naturaltime(c.date),
                f"+{c.additions}/-{c.deletions}",
            )


class PRTable(DataTable):
    """Table for pull request activity."""

    def on_mount(self) -> None:
        self.cursor_type = "row"
        self.add_columns("Author", "Repo", "#", "Title", "State", "Created")

    def populate(self, prs: list[PullRequestActivity]) -> None:
        self.clear()
        for pr in prs:
            self.add_row(
                pr.author,
                pr.repo,
                str(pr.number),
                pr.title,
                pr.state,
                humanize.naturaltime(pr.created_at),
            )


class ReviewTable(DataTable):
    """Table for code review activity."""

    def on_mount(self) -> None:
        self.cursor_type = "row"
        self.add_columns("Reviewer", "Repo", "PR#", "PR Title", "State", "Submitted")

    def populate(self, reviews: list[ReviewActivity]) -> None:
        self.clear()
        for r in reviews:
            self.add_row(
                r.reviewer,
                r.repo,
                str(r.pr_number),
                r.pr_title,
                r.state,
                humanize.naturaltime(r.submitted_at),
            )


class IssueTable(DataTable):
    """Table for issue activity."""

    def on_mount(self) -> None:
        self.cursor_type = "row"
        self.add_columns("Author", "Assignee", "Repo", "#", "Title", "State", "Created")

    def populate(self, issues: list[IssueActivity]) -> None:
        self.clear()
        for i in issues:
            self.add_row(
                i.author,
                i.assignee or "-",
                i.repo,
                str(i.number),
                i.title,
                i.state,
                humanize.naturaltime(i.created_at),
            )


class RepoStatsTable(DataTable):
    """Table for repo-level statistics."""

    def on_mount(self) -> None:
        self.cursor_type = "row"
        self.add_columns(
            "Repo", "Language", "Stars", "Forks",
            "Issues", "PRs", "Contributors", "Last Push",
        )

    def populate(self, summaries: list[OrgRepoSummary]) -> None:
        self.clear()
        for s in summaries:
            self.add_row(
                s.name,
                s.language or "-",
                str(s.stars),
                str(s.forks),
                str(s.open_issues),
                str(s.open_prs),
                str(s.contributors),
                humanize.naturaltime(s.last_push) if s.last_push else "-",
            )
