# sman

A terminal UI for GitHub management and developer activity reporting. Skip the browser — manage repos, track commits, review PRs, and report on your team's activity from the terminal.

Built with [Textual](https://textual.textualize.io/) and [PyGitHub](https://pygithub.readthedocs.io/). Supports multiple GitHub orgs and accounts.

## Features

- **Repo management** — List, create, and inspect repos without leaving the terminal
- **Developer reports** — Commits, pull requests, code reviews, and issues across all repos in an org
- **Repo statistics** — Language breakdown, release frequency, branch activity, contributor counts
- **Multi-org** — Switch between multiple GitHub orgs/personal accounts with a keypress
- **Date range filtering** — Reports support custom ranges and presets (7/30/90 days)
- **Caching** — In-memory TTL cache keeps the UI snappy and respects GitHub rate limits

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (package manager)
- A GitHub [personal access token](https://github.com/settings/tokens) with `repo` scope

## Install

```bash
git clone https://github.com/your-user/github-sman.git
cd github-sman
uv sync
```

## Configuration

sman stores its config at `~/.config/sman/config.toml`. You can set it up through the TUI (press `s` for settings) or create the file manually:

```toml
[general]
default_org = "my-company"
cache_ttl_seconds = 300

[[orgs]]
name = "my-company"
token = "ghp_your_token_here"
type = "org"

[[orgs]]
name = "personal"
token_env = "SMAN_PERSONAL_TOKEN"
type = "user"
```

Each org entry needs:
- `name` — The GitHub org name or your username
- `token` — A personal access token, **or** `token_env` — the name of an environment variable containing the token
- `type` — `"org"` for an organization, `"user"` for a personal account

The config file is created with `600` permissions (owner-only read/write).

## Usage

```bash
# Launch the TUI
uv run sman

# Print version
uv run sman --version
```

### Keyboard shortcuts

| Key | Action |
|---|---|
| `q` | Quit |
| `o` | Switch org |
| `r` | Repos screen |
| `d` | Reports screen |
| `s` | Settings screen |
| `c` | Create repo (from repos screen) |
| `Ctrl+R` | Refresh current data |
| `Escape` | Go back |

### Screens

**Home** — Shows the current org and navigation to other screens.

**Repos** — Lists all repositories for the current org sorted by last update. Select a row to see detailed info (stars, forks, size, topics, dates). Press `c` to create a new repo.

**Reports** — Five tabs of developer activity data:
- **Commits** — Who committed what, when, with line change counts
- **Pull Requests** — Open/merged/closed PRs by author
- **Reviews** — Code review activity (approvals, change requests, comments) by reviewer
- **Issues** — Issue creation, assignment, and closure by author
- **Repo Stats** — Per-repo overview (language, stars, forks, open PRs, contributors)

Select a date range or use presets (last 7/30/90 days) and press **Go** to fetch.

**Settings** — Add, edit, or remove GitHub org configurations and tokens.

## Development

```bash
# Install dependencies
uv sync

# Run the app
uv run sman

# Lint
uv run ruff check src/ tests/

# Auto-fix lint issues
uv run ruff check --fix src/ tests/

# Run tests
uv run pytest

# Run a specific test
uv run pytest -k "test_save_and_load"
```

## License

[GPL-3.0](LICENSE)
