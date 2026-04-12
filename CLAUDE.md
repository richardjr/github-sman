# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

**github-sman** — A Textual TUI for GitHub management and developer activity reporting. Replaces common GitHub web UI actions with a fast terminal interface. Supports multiple GitHub orgs/accounts.

## Tech Stack

- Python 3.12+, Textual (TUI), PyGitHub (GitHub REST API)
- uv for package management, hatchling for builds
- Ruff for linting, pytest for tests
- Config: TOML (`~/.config/sman/config.toml`)

## Commands

```bash
uv sync                    # Install all dependencies
uv run sman                # Launch the TUI
uv run sman --version      # Print version
uv run ruff check src/     # Lint
uv run ruff check --fix src/  # Auto-fix lint issues
uv run pytest              # Run tests
uv run pytest tests/test_cache.py  # Run a single test file
uv run pytest -k "test_name"       # Run a specific test
```

## Architecture

### Package layout (`src/sman/`)

```
__init__.py       → Package init with __version__
__main__.py       → Entry point for `python -m sman`
cli.py            → CLI argument parser (argparse → SmanApp.run())
app.py            → Textual App subclass, screen registration, org switching
config.py         → TOML config load/save, OrgConfig/Config dataclasses, XDG paths
git_status.py     → Local git status parsing (GitFile, GitLocalStatus dataclasses)
local_repo.py     → Local repo helpers (has_claude_md, launch_terminal)
```

#### `github/` — API layer (returns plain dataclasses, never PyGitHub objects)

```
client.py         → GitHubClient dataclass (token auth, dual cache per client)
                    - from_config() factory, get_org(), rate_limit_remaining/reset()
cache.py          → In-memory TTL cache (Cache class, monotonic time expiry)
                    - get/set/invalidate/invalidate_prefix/clear
persistent_cache.py → Disk-backed pickle cache (PersistentCache, no auto-expiry)
                    - get returns (value, cached_at_ts), atomic saves
                    - default_cache_dir() → ~/.cache/sman/
repos.py          → Repo list/create/detail
                    - RepoInfo, RepoDetail, ListReposResult, RepoDetailResult dataclasses
                    - list_repos (persistent cache-first), get_repo_detail (fetch + fallback)
                    - get_cached_repo_detail (read-only), create_repo
                    - get_excluded_repos/set_excluded_repos/toggle_repo_excluded
                    - get_report_repo_names (filtered by exclusion set)
activity.py       → Commits, PRs, code reviews
                    - CommitActivity, PullRequestActivity, ReviewActivity dataclasses
                    - CommitResult, PullRequestResult, ReviewResult (cache wrappers)
                    - fetch_commits/fetch_pull_requests/fetch_reviews
                      (parallel via ThreadPoolExecutor, persistent+memory cache, repo filtering)
                    - get_cached_commits/get_cached_pull_requests/get_cached_reviews
issues.py         → Issue tracking
                    - IssueActivity dataclass, IssueResult (cache wrapper)
                    - fetch_issues (parallel, persistent+memory cache, repo filtering)
                    - get_cached_issues
stats.py          → Repo-level statistics
                    - RepoStats, OrgRepoSummary dataclasses, OrgRepoSummaryResult
                    - fetch_repo_stats (single repo), fetch_org_repo_summaries (all repos)
                    - get_cached_org_repo_summaries
```

#### `screens/` — Textual Screen subclasses

```
home.py           → HomeScreen — landing page with org info + nav buttons
                    Bindings: r=repos, d=reports, s=settings
repos.py          → RepoListScreen — repo list with status/local/report columns
                    Bindings: c=create, r=refresh, e=toggle report inclusion
                  → RepoDetailScreen — full repo detail + local git status
                    Bindings: g=clone, c=claude, n=nvim, t=terminal, r=refresh
                  → RepoCreateScreen — form to create new repos
reports.py        → ReportsScreen — tabbed reports with date range filtering
                    5 tabs: Commits, PRs, Reviews, Issues, Repo Stats
                    Cache-first loading + background refresh
                    Bindings: ctrl+r=refresh
settings.py       → SettingsScreen — general config + org CRUD
help.py           → HelpScreen — modal with keybinding reference
```

#### `widgets/` — Reusable Textual widgets

```
org_switcher.py   → OrgSwitcher(Static) — org selector dropdown, emits OrgChanged
date_range.py     → DateRange(Static) — date inputs + presets, emits DateRangeChanged
repo_table.py     → RepoTable(DataTable) — columns: S, R, Local, Name, Language, Stars, etc.
                    populate(repos, work_dir, persistent_cache, excluded_repos)
report_table.py   → CommitTable, PRTable, ReviewTable, IssueTable, RepoStatsTable
                    Each has on_mount() + populate(data_list)
```

#### `styles/`

```
app.tcss          → Textual CSS stylesheet
```

### Key design patterns

- **GitHub API boundary**: All `github/` modules return plain dataclasses. PyGitHub objects never leak into screens/widgets. This makes caching simple and keeps the TUI decoupled from the API library.
- **Multi-org**: `SmanApp` holds a `dict[str, GitHubClient]` — switching orgs reuses cached clients. Each client has its own TTL cache and persistent cache (`~/.cache/sman/{org}.pkl`).
- **Async data loading**: GitHub API calls run in Textual workers (background threads) via `self.run_worker(..., thread=True)`. Results are pushed to the UI with `self.app.call_from_thread()`.
- **Concurrent fetching**: Report data is fetched across repos in parallel using `ThreadPoolExecutor(max_workers=5)`.
- **Config**: Stored at `~/.config/sman/config.toml` (respects `XDG_CONFIG_HOME`). Tokens can be inline or referenced via env var (`token_env` field). File is `chmod 600`.
- **Dual caching**: In-memory `Cache` (TTL-based, fast, lost on restart) + `PersistentCache` (pickle on disk, no expiry, survives restarts). Repos and reports use cache-first pattern: show persistent cache instantly, refresh in background.
- **Report filtering**: Repos can be excluded from reports via persistent cache (`excluded_repos:{org}` key). Toggled with `e` on repos list.

### Screen flow

```
sman → HomeScreen (default)
         ├→ RepoListScreen → RepoDetailScreen
         ├→ RepoCreateScreen
         ├→ ReportsScreen (5 tabs: Commits, PRs, Reviews, Issues, Repo Stats)
         └→ SettingsScreen
```

Global keybindings: `q` quit, `o` switch org, `r` repos, `d` reports, `s` settings, `escape` back, `ctrl+r` refresh.

### Config format

```toml
[general]
default_org = "my-company"
cache_ttl_seconds = 300

[[orgs]]
name = "my-company"
token = "ghp_xxx"
type = "org"       # or "user" for personal accounts

[[orgs]]
name = "personal"
token_env = "SMAN_PERSONAL_TOKEN"
type = "user"
```

## Lint rules

Ruff with `E`, `F`, `I`, `UP` rule sets. Line length is the default 88 (not configured explicitly — it's ruff's default).
