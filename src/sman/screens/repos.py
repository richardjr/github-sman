"""Repo management screens — list, detail, create."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import (
    Button,
    Checkbox,
    DataTable,
    Input,
    Label,
    LoadingIndicator,
    Static,
)

from sman.github.repos import (
    CreateRepoParams,
    RepoInfo,
    create_repo,
    get_repo_detail,
    list_repos,
)
from sman.widgets.repo_table import RepoTable


class RepoListScreen(Screen):
    """Screen showing all repos for the current org."""

    BINDINGS = [
        ("c", "create_repo", "Create Repo"),
        ("ctrl+r", "refresh", "Refresh"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="repo-list-container"):
            yield Static("Repositories", classes="title")
            yield LoadingIndicator(id="repo-loading")
            yield RepoTable(id="repo-table")

    def on_mount(self) -> None:
        self.query_one("#repo-table", RepoTable).display = False
        self._load_repos()

    def on_screen_resume(self) -> None:
        self._load_repos()

    def _load_repos(self) -> None:
        client = getattr(self.app, "current_client", None)
        if not client:
            self.query_one("#repo-loading", LoadingIndicator).display = False
            return
        self.query_one("#repo-loading", LoadingIndicator).display = True
        self.run_worker(self._fetch_repos, thread=True)

    async def _fetch_repos(self) -> None:
        client = self.app.current_client
        if not client:
            return
        repos = list_repos(client)
        self.app.call_from_thread(self._display_repos, repos)

    def _display_repos(self, repos: list[RepoInfo]) -> None:
        self.query_one("#repo-loading", LoadingIndicator).display = False
        table = self.query_one("#repo-table", RepoTable)
        table.display = True
        table.populate(repos)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.row_key and event.row_key.value:
            self.app.push_screen(RepoDetailScreen(event.row_key.value))

    def action_create_repo(self) -> None:
        self.app.push_screen(RepoCreateScreen())

    def action_refresh(self) -> None:
        client = getattr(self.app, "current_client", None)
        if client:
            client.cache.invalidate_prefix(f"repos:{client.name}")
        self._load_repos()


class RepoDetailScreen(Screen):
    """Detail view for a single repository."""

    def __init__(self, repo_name: str) -> None:
        super().__init__()
        self._repo_name = repo_name

    def compose(self) -> ComposeResult:
        with Vertical(id="repo-detail-container"):
            yield Static(f"Repository: {self._repo_name}", classes="title")
            yield LoadingIndicator(id="detail-loading")
            yield Static("", id="detail-content")

    def on_mount(self) -> None:
        self.run_worker(self._fetch_detail, thread=True)

    async def _fetch_detail(self) -> None:
        client = self.app.current_client
        if not client:
            return
        detail = get_repo_detail(client, self._repo_name)
        self.app.call_from_thread(self._display_detail, detail)

    def _display_detail(self, detail) -> None:
        self.query_one("#detail-loading", LoadingIndicator).display = False
        content = self.query_one("#detail-content", Static)

        import humanize

        lines = [
            f"[bold]{detail.full_name}[/bold]",
            f"  {detail.description}" if detail.description else "",
            "",
            f"  Language:   {detail.language or 'N/A'}",
            f"  Stars:      {detail.stars}",
            f"  Forks:      {detail.forks}",
            f"  Issues:     {detail.open_issues}",
            f"  Size:       {humanize.naturalsize(detail.size_kb * 1024)}",
            f"  Branch:     {detail.default_branch}",
            f"  Visibility: {'private' if detail.private else 'public'}",
            f"  Archived:   {'yes' if detail.archived else 'no'}",
            "",
            f"  Created:    {detail.created_at:%Y-%m-%d}",
            f"  Updated:    {humanize.naturaltime(detail.updated_at)}",
            f"  Pushed:     {humanize.naturaltime(detail.pushed_at)}",
        ]
        if detail.topics:
            lines.append(f"  Topics:     {', '.join(detail.topics)}")
        lines.append(f"\n  URL: {detail.html_url}")

        content.update("\n".join(lines))


class RepoCreateScreen(Screen):
    """Form for creating a new repository."""

    def compose(self) -> ComposeResult:
        with Vertical(id="repo-create-form"):
            yield Static("Create Repository", classes="title")
            yield Label("Name")
            yield Input(placeholder="my-new-repo", id="repo-name")
            yield Label("Description")
            yield Input(placeholder="A short description", id="repo-desc")
            yield Checkbox("Private", value=True, id="repo-private")
            yield Checkbox("Initialize with README", value=True, id="repo-init")
            yield Button("Create", variant="success", id="btn-create")
            yield Static("", id="create-status")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-create":
            name = self.query_one("#repo-name", Input).value.strip()
            if not name:
                status = self.query_one("#create-status", Static)
                status.update("[red]Name is required[/red]")
                return
            desc = self.query_one("#repo-desc", Input).value.strip()
            private = self.query_one("#repo-private", Checkbox).value
            auto_init = self.query_one("#repo-init", Checkbox).value

            params = CreateRepoParams(
                name=name, description=desc, private=private, auto_init=auto_init
            )
            self.query_one("#create-status", Static).update("Creating...")
            self.run_worker(lambda: self._create(params), thread=True)

    def _create(self, params: CreateRepoParams) -> None:
        client = self.app.current_client
        if not client:
            self.app.call_from_thread(
                self.query_one("#create-status", Static).update,
                "[red]No org connected[/red]",
            )
            return
        try:
            repo = create_repo(client, params)
            self.app.call_from_thread(
                self.query_one("#create-status", Static).update,
                f"[green]Created {repo.full_name}[/green]",
            )
        except Exception as e:
            self.app.call_from_thread(
                self.query_one("#create-status", Static).update,
                f"[red]Error: {e}[/red]",
            )
