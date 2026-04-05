"""Local git status queries for cloned repositories.

Runs ``git fetch`` (best-effort) and ``git status --branch --porcelain=v1``
against a local checkout, parsing the result into a plain dataclass so the
Textual layer can render it without depending on subprocess semantics.
Framework-free so it can be unit-tested in isolation.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sman.github.persistent_cache import PersistentCache

FETCH_TIMEOUT_SECONDS = 15
STATUS_TIMEOUT_SECONDS = 5


@dataclass
class GitFile:
    """One entry from ``git status --porcelain``."""

    code: str  # two-character code, e.g. " M", "M ", "??", "A ", "UU"
    path: str  # path relative to repo root; renames stored as "old -> new"


@dataclass
class GitLocalStatus:
    """Parsed result of a local git status query."""

    branch: str = ""
    upstream: str = ""  # e.g. "origin/main" — empty when no upstream configured
    ahead: int = 0
    behind: int = 0
    files: list[GitFile] = field(default_factory=list)
    fetch_error: str = ""  # non-fatal: fetch failed but status still ran
    error: str = ""  # fatal: status itself failed (not a repo, git missing, ...)


def get_local_status(repo_path: Path) -> GitLocalStatus:
    """Fetch then read ``git status --branch --porcelain=v1`` for ``repo_path``.

    Never raises: all failures are reported via ``error`` or ``fetch_error``
    so the caller can render whatever partial information is available.
    """
    if not (repo_path / ".git").exists():
        return GitLocalStatus(error="not a git repository")

    status = GitLocalStatus()

    try:
        subprocess.run(
            ["git", "-C", str(repo_path), "fetch", "--quiet"],
            capture_output=True,
            text=True,
            timeout=FETCH_TIMEOUT_SECONDS,
            check=True,
        )
    except subprocess.TimeoutExpired:
        status.fetch_error = f"fetch timed out after {FETCH_TIMEOUT_SECONDS}s"
    except subprocess.CalledProcessError as e:
        status.fetch_error = _last_line(e.stderr or str(e))
    except FileNotFoundError:
        status.error = "git not installed"
        return status

    try:
        result = subprocess.run(
            ["git", "-C", str(repo_path), "status", "--branch", "--porcelain=v1"],
            capture_output=True,
            text=True,
            timeout=STATUS_TIMEOUT_SECONDS,
            check=True,
        )
    except subprocess.TimeoutExpired:
        status.error = "git status timed out"
        return status
    except subprocess.CalledProcessError as e:
        status.error = _last_line(e.stderr or str(e))
        return status
    except FileNotFoundError:
        status.error = "git not installed"
        return status

    _parse_porcelain(result.stdout, status)
    return status


def _last_line(text: str, limit: int = 120) -> str:
    """Return the last non-empty line of ``text``, truncated to ``limit`` chars."""
    lines = [line for line in text.strip().splitlines() if line.strip()]
    if not lines:
        return ""
    return lines[-1][:limit]


def _parse_porcelain(output: str, status: GitLocalStatus) -> None:
    """Parse ``git status --branch --porcelain=v1`` output into ``status``.

    The first line is always ``## <branch>[...<upstream>[ [ahead N, behind M]]]``
    or ``## HEAD (no branch)`` when detached. Subsequent lines are ``XY <path>``
    where ``XY`` is a two-character code and ``path`` may contain ``" -> "`` for
    renames.
    """
    lines = output.splitlines()
    if lines and lines[0].startswith("## "):
        _parse_branch_line(lines[0][3:], status)
        lines = lines[1:]
    for line in lines:
        if len(line) >= 3:
            status.files.append(GitFile(code=line[:2], path=line[3:]))


def cache_key(repo_name: str) -> str:
    """Return the PersistentCache key used to store a repo's git status."""
    return f"git_status:{repo_name}"


def get_cached_local_status(
    cache: PersistentCache, repo_name: str
) -> GitLocalStatus | None:
    """Return the cached GitLocalStatus for ``repo_name``, or None if absent."""
    entry = cache.get(cache_key(repo_name))
    if entry is None:
        return None
    value, _ = entry
    return value if isinstance(value, GitLocalStatus) else None


def cache_local_status(
    cache: PersistentCache, repo_name: str, status: GitLocalStatus
) -> None:
    """Persist ``status`` for ``repo_name``."""
    cache.set(cache_key(repo_name), status)


def status_char(status: GitLocalStatus | None) -> tuple[str, str]:
    """Return a (single-character, Rich colour name) indicator for a list cell.

    Priority order (most urgent wins):
        1. No cache                → "?" dim
        2. Unavailable (error)     → "-" dim
        3. Conflict in the index   → "!" red
        4. Uncommitted changes     → "●" yellow
        5. Diverged (ahead+behind) → "⇅" red
        6. Behind upstream         → "↓" yellow
        7. Ahead of upstream       → "↑" green
        8. Clean + synced          → "✓" green
    """
    if status is None:
        return ("?", "bright_black")
    if status.error:
        return ("-", "bright_black")
    has_conflict = any(
        "U" in f.code or f.code in ("DD", "AA") for f in status.files
    )
    if has_conflict:
        return ("!", "red")
    if status.files:
        return ("●", "yellow")
    if status.ahead and status.behind:
        return ("⇅", "red")
    if status.behind:
        return ("↓", "yellow")
    if status.ahead:
        return ("↑", "green")
    return ("✓", "green")


def _parse_branch_line(body: str, status: GitLocalStatus) -> None:
    """Populate branch/upstream/ahead/behind from the ``## ...`` line body."""
    track = ""
    if " [" in body and body.endswith("]"):
        idx = body.rindex(" [")
        track = body[idx + 2 : -1]
        body = body[:idx]
    if "..." in body:
        status.branch, status.upstream = body.split("...", 1)
    else:
        status.branch = body
    for part in track.split(", "):
        if part.startswith("ahead "):
            try:
                status.ahead = int(part[len("ahead "):])
            except ValueError:
                pass
        elif part.startswith("behind "):
            try:
                status.behind = int(part[len("behind "):])
            except ValueError:
                pass
