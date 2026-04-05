"""Reports screen — tabbed view of developer activity and repo stats."""

from __future__ import annotations

from datetime import datetime

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Footer, LoadingIndicator, Static, TabbedContent, TabPane

from sman.github.activity import fetch_commits, fetch_pull_requests, fetch_reviews
from sman.github.issues import fetch_issues
from sman.github.stats import fetch_org_repo_summaries
from sman.widgets.date_range import DateRange
from sman.widgets.report_table import (
    CommitTable,
    IssueTable,
    PRTable,
    RepoStatsTable,
    ReviewTable,
)


class ReportsScreen(Screen):
    """Tabbed reporting screen with date range filtering."""

    BINDINGS = [
        Binding("ctrl+r", "refresh", "Refresh", key_display="^R"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="reports-container"):
            yield Static("Developer Reports", classes="title")
            yield DateRange(id="date-range")
            yield LoadingIndicator(id="report-loading")
            with TabbedContent():
                with TabPane("Commits", id="tab-commits"):
                    yield CommitTable(id="commit-table")
                with TabPane("Pull Requests", id="tab-prs"):
                    yield PRTable(id="pr-table")
                with TabPane("Reviews", id="tab-reviews"):
                    yield ReviewTable(id="review-table")
                with TabPane("Issues", id="tab-issues"):
                    yield IssueTable(id="issue-table")
                with TabPane("Repo Stats", id="tab-stats"):
                    yield RepoStatsTable(id="stats-table")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#report-loading", LoadingIndicator).display = False

    def on_date_range_date_range_changed(
        self, event: DateRange.DateRangeChanged
    ) -> None:
        self._load_data(event.since, event.until)

    def _load_data(self, since: datetime, until: datetime) -> None:
        client = getattr(self.app, "current_client", None)
        if not client:
            self.app.notify("No org connected", severity="error")
            return
        self.query_one("#report-loading", LoadingIndicator).display = True
        self.run_worker(lambda: self._fetch_all(since, until), thread=True)

    def _fetch_all(self, since: datetime, until: datetime) -> None:
        client = self.app.current_client
        if not client:
            return

        try:
            commits = fetch_commits(client, since, until)
            self.app.call_from_thread(
                self.query_one("#commit-table", CommitTable).populate, commits
            )
        except Exception:
            pass

        try:
            prs = fetch_pull_requests(client, since, until)
            self.app.call_from_thread(
                self.query_one("#pr-table", PRTable).populate, prs
            )
        except Exception:
            pass

        try:
            reviews = fetch_reviews(client, since, until)
            self.app.call_from_thread(
                self.query_one("#review-table", ReviewTable).populate, reviews
            )
        except Exception:
            pass

        try:
            issues = fetch_issues(client, since, until)
            self.app.call_from_thread(
                self.query_one("#issue-table", IssueTable).populate, issues
            )
        except Exception:
            pass

        try:
            summaries = fetch_org_repo_summaries(client)
            self.app.call_from_thread(
                self.query_one("#stats-table", RepoStatsTable).populate, summaries
            )
        except Exception:
            pass

        self.app.call_from_thread(self._hide_loading)

    def _hide_loading(self) -> None:
        self.query_one("#report-loading", LoadingIndicator).display = False

    def action_refresh(self) -> None:
        client = getattr(self.app, "current_client", None)
        if client:
            client.cache.clear()
        try:
            since, until = self.query_one("#date-range", DateRange).get_range()
            self._load_data(since, until)
        except ValueError:
            pass
