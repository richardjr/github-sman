"""Repo management screens — list, detail, create."""

from __future__ import annotations

import humanize
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import (
    Button,
    Checkbox,
    DataTable,
    Footer,
    Input,
    Label,
    LoadingIndicator,
    Static,
)

from sman.git_status import (
    GitFile,
    GitLocalStatus,
    cache_local_status,
    get_cached_local_status,
    get_local_status,
)
from sman.github.repos import (
    CreateRepoParams,
    ListReposResult,
    RepoDetailResult,
    create_repo,
    get_cached_repo_detail,
    get_repo_detail,
    list_repos,
)
from sman.local_repo import has_claude_md, launch_terminal
from sman.widgets.repo_table import RepoTable


def _classify_file(code: str) -> str:
    """Return a Textual markup colour for a porcelain two-char status code."""
    if code == "??":
        return "dim"
    if "U" in code or code in ("DD", "AA"):
        return "red"
    # Prefer the rightmost non-space column so mixed states (e.g. "MM") are
    # highlighted as unstaged — matches how `git status` colours them.
    if len(code) == 2 and code[1] != " ":
        return "yellow"
    if code[0] not in (" ", "?"):
        return "green"
    return "white"


def _render_file_line(f: GitFile) -> str:
    colour = _classify_file(f.code)
    # Escape square brackets so Textual markup doesn't treat the code as a tag.
    code_display = f.code.replace("[", r"\[")
    return f"  [{colour}]{code_display}[/{colour}] {f.path}"


def _render_git_status(status: GitLocalStatus) -> list[str]:
    """Render a GitLocalStatus into a list of markup lines for #detail-content."""
    lines: list[str] = ["", "  [bold]Local state[/bold]"]

    if status.error:
        lines.append(f"  [red]Git status unavailable: {status.error}[/red]")
        return lines

    branch_display = status.branch or "(unknown)"
    if status.upstream:
        branch_display = f"{branch_display} → {status.upstream}"
    counters: list[str] = []
    if status.ahead:
        counters.append(f"[green]↑{status.ahead}[/green]")
    if status.behind:
        counters.append(f"[yellow]↓{status.behind}[/yellow]")
    if counters:
        branch_display = f"{branch_display}  " + " ".join(counters)
    lines.append(f"  Branch:     {branch_display}")

    if status.fetch_error:
        lines.append(f"  [yellow]Fetch warning: {status.fetch_error}[/yellow]")

    lines.append("")
    if not status.files:
        lines.append("  [dim]Working tree clean[/dim]")
        return lines

    for f in status.files:
        lines.append(_render_file_line(f))
    return lines


class RepoListScreen(Screen):
    """Screen showing all repos for the current org."""

    BINDINGS = [
        Binding("c", "create_repo", "Create Repo"),
        Binding("r", "refresh", "Refresh"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="repo-list-container"):
            yield Static("Repositories", classes="title")
            yield Static("", id="repo-status")
            yield LoadingIndicator(id="repo-loading")
            yield RepoTable(id="repo-table")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#repo-table", RepoTable).display = False
        self._load_repos()

    def on_screen_resume(self) -> None:
        self._load_repos()

    def _load_repos(self, force_refresh: bool = False) -> None:
        client = getattr(self.app, "current_client", None)
        if not client:
            self.query_one("#repo-loading", LoadingIndicator).display = False
            return
        self.query_one("#repo-loading", LoadingIndicator).display = True
        self.run_worker(
            lambda: self._fetch_repos(force_refresh), thread=True
        )

    def _fetch_repos(self, force_refresh: bool) -> None:
        client = self.app.current_client
        if not client:
            return
        try:
            result = list_repos(client, force_refresh=force_refresh)
        except Exception as e:
            self.app.call_from_thread(self._display_error, str(e))
            return
        self.app.call_from_thread(self._display_repos, result)

    def _display_repos(self, result: ListReposResult) -> None:
        self.query_one("#repo-loading", LoadingIndicator).display = False
        table = self.query_one("#repo-table", RepoTable)
        table.display = True
        client = getattr(self.app, "current_client", None)
        table.populate(
            result.repos,
            self.app.config.resolved_work_dir,
            persistent_cache=client.persistent_cache if client else None,
        )

        status = self.query_one("#repo-status", Static)
        relative = humanize.naturaltime(result.cached_at)
        if result.from_cache:
            status.update(
                f"[dim]Cached — updated {relative}. "
                "Press [bold]r[/bold] to refresh.[/dim]"
            )
        else:
            status.update(f"[green]Fresh — fetched {relative}[/green]")

    def _display_error(self, message: str) -> None:
        self.query_one("#repo-loading", LoadingIndicator).display = False
        self.query_one("#repo-status", Static).update(
            f"[red]Failed to load repos: {message}[/red]"
        )

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.row_key and event.row_key.value:
            self.app.push_screen(RepoDetailScreen(event.row_key.value))

    def action_create_repo(self) -> None:
        self.app.push_screen(RepoCreateScreen())

    def action_refresh(self) -> None:
        self._load_repos(force_refresh=True)


class RepoDetailScreen(Screen):
    """Detail view for a single repository."""

    BINDINGS = [
        Binding("g", "clone_repo", "Clone"),
        Binding("c", "claude_terminal", "Claude"),
        Binding("n", "nvim_terminal", "Neovim"),
        Binding("r", "refresh_detail", "Refresh"),
    ]

    def __init__(self, repo_name: str) -> None:
        super().__init__()
        self._repo_name = repo_name
        self._detail = None
        self._git_status: GitLocalStatus | None = None

    def compose(self) -> ComposeResult:
        with Vertical(id="repo-detail-container"):
            yield Static(f"Repository: {self._repo_name}", classes="title")
            yield LoadingIndicator(id="detail-loading")
            yield Static("", id="detail-content")
            yield Static("", id="clone-status")
        yield Footer()

    def on_mount(self) -> None:
        self._git_status = None

        # Cache-first: if we already have a cached GitHub detail for this
        # repo, render it immediately (with the loading spinner still
        # running) so the page appears instantly. The worker below then
        # refreshes both the GitHub detail and the local git status.
        client = getattr(self.app, "current_client", None)
        if client is not None:
            cached_detail = get_cached_repo_detail(client, self._repo_name)
            if cached_detail is not None:
                # git_status entries are keyed on the short repo name (the
                # on-disk directory name), not the owner/name full form we
                # receive here, so normalise before looking it up.
                short_name = self._repo_name.rsplit("/", 1)[-1]
                self._git_status = get_cached_local_status(
                    client.persistent_cache, short_name
                )
                self._display_detail(cached_detail, updating=True)

        self.run_worker(self._fetch_detail, thread=True)

    def _fetch_detail(self) -> None:
        client = self.app.current_client
        if not client:
            return
        try:
            result = get_repo_detail(client, self._repo_name)
        except Exception as e:
            self.app.call_from_thread(self._display_error, str(e))
            return

        # Best-effort local git status — runs inside the same thread worker
        # so the detail view stays responsive while we fetch/parse.
        work_dir = self.app.config.resolved_work_dir
        if work_dir:
            local_path = work_dir / result.detail.name
            if local_path.is_dir():
                self._git_status = get_local_status(local_path)
                cache_local_status(
                    client.persistent_cache,
                    result.detail.name,
                    self._git_status,
                )

        self.app.call_from_thread(self._display_detail, result, False)

    def _display_error(self, message: str) -> None:
        self.query_one("#detail-loading", LoadingIndicator).display = False
        self.query_one("#detail-content", Static).update(
            f"[red]Failed to load repo: {message}[/red]"
        )

    def _display_detail(
        self, result: RepoDetailResult, updating: bool = False
    ) -> None:
        detail = result.detail
        self._detail = detail
        # Keep the spinner visible while a background refresh is still running
        # so the user sees that cached content is being updated.
        self.query_one("#detail-loading", LoadingIndicator).display = updating
        content = self.query_one("#detail-content", Static)

        import humanize

        work_dir = self.app.config.resolved_work_dir
        local_path = work_dir / detail.name if work_dir else None
        is_cloned = local_path is not None and local_path.is_dir()

        lines: list[str] = []
        if updating:
            lines.append(
                "[dim]⟳ Showing cached data — refreshing from "
                "GitHub and local git…[/dim]"
            )
            lines.append("")
        elif result.from_cache:
            lines.append(
                f"[yellow]⚠ Showing cached data from "
                f"{humanize.naturaltime(result.cached_at)} "
                f"(remote fetch failed)[/yellow]"
            )
            lines.append("")
        lines += [
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
        lines.append(f"\n  URL:   {detail.html_url}")
        lines.append(f"  SSH:   {detail.ssh_url}")
        if is_cloned:
            lines.append(f"\n  [green]Cloned at {local_path}[/green]")
            if has_claude_md(local_path):
                lines.append("  [cyan]Claude repo (CLAUDE.md present)[/cyan]")
            lines.append(
                "  [dim]Press [bold]c[/bold] for claude, "
                "[bold]n[/bold] for nvim[/dim]"
            )
            if self._git_status is not None:
                lines.extend(_render_git_status(self._git_status))
        elif work_dir:
            lines.append(
                "\n  [dim]Not cloned locally"
                " — press [bold]g[/bold] to clone[/dim]"
            )

        content.update("\n".join(lines))

    def action_refresh_detail(self) -> None:
        """Re-fetch repo detail from GitHub and re-read local git status."""
        self.query_one("#detail-loading", LoadingIndicator).display = True
        self.run_worker(self._fetch_detail, thread=True)

    def action_clone_repo(self) -> None:
        """Clone the repo into work_dir."""
        if not self._detail:
            return
        work_dir = self.app.config.resolved_work_dir
        if not work_dir:
            self.app.notify("Set work_dir in Settings first", severity="error")
            return
        local_path = work_dir / self._detail.name
        if local_path.is_dir():
            self.app.notify("Already cloned", severity="warning")
            return
        status = self.query_one("#clone-status", Static)
        status.update("[yellow]Cloning...[/yellow]")
        self.run_worker(
            lambda: self._run_clone(self._detail.ssh_url, work_dir, local_path),
            thread=True,
        )

    def _run_clone(self, ssh_url: str, work_dir, local_path) -> None:
        import subprocess

        try:
            subprocess.run(
                ["git", "clone", ssh_url],
                cwd=work_dir,
                capture_output=True,
                text=True,
                check=True,
            )
            self.app.call_from_thread(
                self.query_one("#clone-status", Static).update,
                f"[green]Cloned to {local_path}[/green]",
            )
        except subprocess.CalledProcessError as e:
            msg = e.stderr.strip() if e.stderr else str(e)
            self.app.call_from_thread(
                self.query_one("#clone-status", Static).update,
                f"[red]Clone failed: {msg}[/red]",
            )

    def action_claude_terminal(self) -> None:
        """Open a new terminal window running `claude` in the local repo dir."""
        self._launch_in_terminal(["claude"], label="claude")

    def action_nvim_terminal(self) -> None:
        """Open a new terminal window running `nvim .` in the local repo dir."""
        self._launch_in_terminal(["nvim", "."], label="nvim")

    def _launch_in_terminal(self, argv: list[str], label: str) -> None:
        if not self._detail:
            return
        work_dir = self.app.config.resolved_work_dir
        if not work_dir:
            self.app.notify("Set work_dir in Settings first", severity="error")
            return
        local_path = work_dir / self._detail.name
        if not local_path.is_dir():
            self.app.notify("Repo not cloned locally", severity="warning")
            return
        try:
            launch_terminal(local_path, argv, self.app.config.terminal)
            self.app.notify(f"Launched {label} in {local_path.name}")
        except Exception as e:
            self.app.notify(
                f"Terminal launch failed: {e}", severity="error"
            )


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
        yield Footer()

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
