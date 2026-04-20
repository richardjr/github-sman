"""Reports screen — tabbed view of developer activity and repo stats."""

from __future__ import annotations

from datetime import datetime

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Footer, LoadingIndicator, Static, TabbedContent, TabPane

from sman.github.activity import (
    fetch_commits,
    fetch_pull_requests,
    fetch_reviews,
    get_cached_commits,
    get_cached_pull_requests,
    get_cached_reviews,
)
from sman.github.issues import fetch_issues, get_cached_issues
from sman.github.repos import get_report_repo_names
from sman.github.stats import fetch_org_repo_summaries, get_cached_org_repo_summaries
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
            yield Static("", id="report-status")
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
        # Auto-load with default date range
        try:
            since, until = self.query_one("#date-range", DateRange).get_range()
            self._load_data(since, until)
        except (ValueError, Exception):
            pass

    def on_screen_resume(self) -> None:
        try:
            since, until = self.query_one("#date-range", DateRange).get_range()
            self._load_data(since, until)
        except (ValueError, Exception):
            pass

    def on_date_range_date_range_changed(
        self, event: DateRange.DateRangeChanged
    ) -> None:
        self._load_data(event.since, event.until)

    def _load_data(self, since: datetime, until: datetime) -> None:
        client = getattr(self.app, "current_client", None)
        if not client:
            self.app.notify("No org connected", severity="error")
            return

        # Phase 1: show cached data instantly (no network)
        self._show_cached_data(client, since, until)

        # Phase 2: background refresh
        self.query_one("#report-loading", LoadingIndicator).display = True
        self.run_worker(
            lambda: self._fetch_all(since, until, force_refresh=False),
            thread=True,
        )

    def _show_cached_data(self, client, since: datetime, until: datetime) -> None:
        """Populate tables from persistent cache if available."""
        any_cached = False

        cached = get_cached_commits(client, since, until)
        if cached is not None:
            self.query_one("#commit-table", CommitTable).populate(cached.commits)
            any_cached = True

        cached = get_cached_pull_requests(client, since, until)
        if cached is not None:
            self.query_one("#pr-table", PRTable).populate(cached.prs)
            any_cached = True

        cached = get_cached_reviews(client, since, until)
        if cached is not None:
            self.query_one("#review-table", ReviewTable).populate(cached.reviews)
            any_cached = True

        cached = get_cached_issues(client, since, until)
        if cached is not None:
            self.query_one("#issue-table", IssueTable).populate(cached.issues)
            any_cached = True

        cached = get_cached_org_repo_summaries(client)
        if cached is not None:
            self.query_one("#stats-table", RepoStatsTable).populate(
                cached.summaries
            )
            any_cached = True

        status = self.query_one("#report-status", Static)
        if any_cached:
            status.update(
                "[dim]Showing cached data — refreshing from GitHub...[/dim]"
            )
        else:
            status.update("[dim]Fetching from GitHub...[/dim]")

    def _fetch_all(
        self,
        since: datetime,
        until: datetime,
        force_refresh: bool = False,
    ) -> None:
        client = self.app.current_client
        if not client:
            return

        repo_names = get_report_repo_names(client)

        errors: list[str] = []

        try:
            result = fetch_commits(
                client, since, until,
                repo_names=repo_names, force_refresh=force_refresh,
            )
            self.app.call_from_thread(
                self.query_one("#commit-table", CommitTable).populate,
                result.commits,
            )
        except Exception as e:
            errors.append(f"Commits: {e}")

        try:
            result = fetch_pull_requests(
                client, since, until,
                repo_names=repo_names, force_refresh=force_refresh,
            )
            self.app.call_from_thread(
                self.query_one("#pr-table", PRTable).populate, result.prs
            )
        except Exception as e:
            errors.append(f"PRs: {e}")

        try:
            result = fetch_reviews(
                client, since, until,
                repo_names=repo_names, force_refresh=force_refresh,
            )
            self.app.call_from_thread(
                self.query_one("#review-table", ReviewTable).populate,
                result.reviews,
            )
        except Exception as e:
            errors.append(f"Reviews: {e}")

        try:
            result = fetch_issues(
                client, since, until,
                repo_names=repo_names, force_refresh=force_refresh,
            )
            self.app.call_from_thread(
                self.query_one("#issue-table", IssueTable).populate,
                result.issues,
            )
        except Exception as e:
            errors.append(f"Issues: {e}")

        try:
            result = fetch_org_repo_summaries(
                client,
                repo_names=repo_names, force_refresh=force_refresh,
            )
            self.app.call_from_thread(
                self.query_one("#stats-table", RepoStatsTable).populate,
                result.summaries,
            )
        except Exception as e:
            errors.append(f"Stats: {e}")

        self.app.call_from_thread(self._done_loading, errors)

    def _done_loading(self, errors: list[str] | None = None) -> None:
        self.query_one("#report-loading", LoadingIndicator).display = False
        status = self.query_one("#report-status", Static)
        if errors:
            msg = "; ".join(errors)
            status.update(f"[red]Errors: {msg}[/red]")
        else:
            status.update("[green]Fresh — fetched just now[/green]")

    def action_refresh(self) -> None:
        client = getattr(self.app, "current_client", None)
        if client:
            client.cache.clear()
            for prefix in (
                "commits:", "prs:", "reviews:", "issues:", "org_summaries:"
            ):
                client.persistent_cache.invalidate_prefix(prefix)
        try:
            since, until = self.query_one("#date-range", DateRange).get_range()
            self._load_data(since, until)
        except ValueError:
            pass
