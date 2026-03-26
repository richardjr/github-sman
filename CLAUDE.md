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
cli.py          → Entry point (argparse → SmanApp.run())
app.py          → Textual App subclass, screen registration, org switching
config.py       → TOML config load/save, OrgConfig dataclass, XDG paths
github/         → API layer (returns plain dataclasses, never PyGitHub objects)
  client.py     → GitHubClient wrapper (token auth, cache per client)
  cache.py      → In-memory TTL cache
  repos.py      → Repo list/create/detail
  activity.py   → Commits, PRs, code reviews
  issues.py     → Issue tracking
  stats.py      → Repo-level statistics
screens/        → Textual Screen subclasses
  home.py       → Landing page with org info + nav
  repos.py      → Repo list, detail, create screens
  reports.py    → Tabbed reports (commits, PRs, reviews, issues, repo stats)
  settings.py   → Org/token CRUD
widgets/        → Reusable Textual widgets
  org_switcher.py → Org selector dropdown
  date_range.py   → Date range input with presets
  repo_table.py   → DataTable for repos
  report_table.py → DataTables for each report type
styles/
  app.tcss      → Textual CSS stylesheet
```

### Key design patterns

- **GitHub API boundary**: All `github/` modules return plain dataclasses. PyGitHub objects never leak into screens/widgets. This makes caching simple and keeps the TUI decoupled from the API library.
- **Multi-org**: `SmanApp` holds a `dict[str, GitHubClient]` — switching orgs reuses cached clients. Each client has its own TTL cache.
- **Async data loading**: GitHub API calls run in Textual workers (background threads) via `self.run_worker(..., thread=True)`. Results are pushed to the UI with `self.app.call_from_thread()`.
- **Concurrent fetching**: Report data is fetched across repos in parallel using `ThreadPoolExecutor(max_workers=5)`.
- **Config**: Stored at `~/.config/sman/config.toml` (respects `XDG_CONFIG_HOME`). Tokens can be inline or referenced via env var (`token_env` field). File is `chmod 600`.

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
