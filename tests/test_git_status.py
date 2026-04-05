"""Tests for sman.git_status."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from sman import git_status
from sman.git_status import (
    GitFile,
    GitLocalStatus,
    _parse_branch_line,
    _parse_porcelain,
    cache_local_status,
    get_cached_local_status,
    get_local_status,
    status_char,
)
from sman.github.persistent_cache import PersistentCache


def _make_repo(tmp_path: Path) -> Path:
    """Create a directory that looks like a git repo to get_local_status."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    return repo


def _ok(stdout: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(
        args=[], returncode=0, stdout=stdout, stderr=""
    )


def _install_fake_run(
    monkeypatch: pytest.MonkeyPatch,
    responses: dict[str, subprocess.CompletedProcess | Exception],
) -> list[list[str]]:
    """Install a fake subprocess.run that dispatches on the subcommand name.

    ``responses`` is keyed by "fetch" or "status". Returns a list that will be
    populated with the argv of each call, for assertions.
    """
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess:
        calls.append(list(cmd))
        # argv shape: ["git", "-C", <path>, "<subcommand>", ...]
        key = cmd[3]
        response = responses[key]
        if isinstance(response, Exception):
            raise response
        return response

    monkeypatch.setattr(git_status.subprocess, "run", fake_run)
    return calls


# ---------------------------------------------------------------------------
# _parse_branch_line — unit tests, no subprocess needed
# ---------------------------------------------------------------------------


def test_parse_branch_line_plain_branch() -> None:
    s = GitLocalStatus()
    _parse_branch_line("main", s)
    assert s.branch == "main"
    assert s.upstream == ""
    assert (s.ahead, s.behind) == (0, 0)


def test_parse_branch_line_with_upstream_no_divergence() -> None:
    s = GitLocalStatus()
    _parse_branch_line("main...origin/main", s)
    assert s.branch == "main"
    assert s.upstream == "origin/main"
    assert (s.ahead, s.behind) == (0, 0)


def test_parse_branch_line_ahead_only() -> None:
    s = GitLocalStatus()
    _parse_branch_line("main...origin/main [ahead 2]", s)
    assert (s.branch, s.upstream) == ("main", "origin/main")
    assert (s.ahead, s.behind) == (2, 0)


def test_parse_branch_line_ahead_and_behind() -> None:
    s = GitLocalStatus()
    _parse_branch_line("feature/x...origin/feature/x [ahead 2, behind 1]", s)
    assert s.branch == "feature/x"
    assert s.upstream == "origin/feature/x"
    assert (s.ahead, s.behind) == (2, 1)


def test_parse_branch_line_detached_head() -> None:
    s = GitLocalStatus()
    _parse_branch_line("HEAD (no branch)", s)
    assert s.branch == "HEAD (no branch)"
    assert s.upstream == ""


# ---------------------------------------------------------------------------
# _parse_porcelain — file list parsing
# ---------------------------------------------------------------------------


def test_parse_porcelain_mixed_file_list() -> None:
    output = (
        "## main...origin/main [ahead 1, behind 2]\n"
        "?? new.py\n"
        " M modified.py\n"
        "A  added.py\n"
        "MM both.py\n"
        "UU conflict.py\n"
        "R  old.py -> new.py\n"
    )
    s = GitLocalStatus()
    _parse_porcelain(output, s)
    assert s.branch == "main"
    assert s.upstream == "origin/main"
    assert (s.ahead, s.behind) == (1, 2)
    codes = [(f.code, f.path) for f in s.files]
    assert codes == [
        ("??", "new.py"),
        (" M", "modified.py"),
        ("A ", "added.py"),
        ("MM", "both.py"),
        ("UU", "conflict.py"),
        ("R ", "old.py -> new.py"),
    ]


def test_parse_porcelain_empty_output_is_clean_tree_without_branch() -> None:
    s = GitLocalStatus()
    _parse_porcelain("", s)
    assert s.branch == ""
    assert s.files == []


# ---------------------------------------------------------------------------
# get_local_status — happy path and failure modes
# ---------------------------------------------------------------------------


def test_get_local_status_not_a_repo(tmp_path: Path) -> None:
    # No .git directory
    result = get_local_status(tmp_path)
    assert result.error == "not a git repository"
    assert result.files == []


def test_get_local_status_happy_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _make_repo(tmp_path)
    calls = _install_fake_run(
        monkeypatch,
        {
            "fetch": _ok(),
            "status": _ok(
                "## main...origin/main [ahead 1]\n M src/foo.py\n?? new.txt\n"
            ),
        },
    )

    result = get_local_status(repo)

    assert result.error == ""
    assert result.fetch_error == ""
    assert result.branch == "main"
    assert result.upstream == "origin/main"
    assert result.ahead == 1
    assert result.behind == 0
    assert [(f.code, f.path) for f in result.files] == [
        (" M", "src/foo.py"),
        ("??", "new.txt"),
    ]
    # Both commands were invoked with `-C <repo>`
    assert calls[0][:4] == ["git", "-C", str(repo), "fetch"]
    assert calls[1][:4] == ["git", "-C", str(repo), "status"]


def test_get_local_status_fetch_failure_is_non_fatal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _make_repo(tmp_path)
    _install_fake_run(
        monkeypatch,
        {
            "fetch": subprocess.CalledProcessError(
                returncode=128,
                cmd=["git", "fetch"],
                stderr="ssh: Could not resolve hostname nope\nfatal: bad\n",
            ),
            "status": _ok("## main\n M foo.py\n"),
        },
    )

    result = get_local_status(repo)

    assert result.error == ""
    assert "fatal: bad" in result.fetch_error
    # Status still ran and populated files
    assert result.branch == "main"
    assert [(f.code, f.path) for f in result.files] == [(" M", "foo.py")]


def test_get_local_status_fetch_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _make_repo(tmp_path)
    _install_fake_run(
        monkeypatch,
        {
            "fetch": subprocess.TimeoutExpired(cmd=["git", "fetch"], timeout=15),
            "status": _ok("## main\n"),
        },
    )

    result = get_local_status(repo)

    assert "timed out" in result.fetch_error
    assert result.error == ""
    assert result.branch == "main"


def test_get_local_status_status_failure_is_fatal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _make_repo(tmp_path)
    _install_fake_run(
        monkeypatch,
        {
            "fetch": _ok(),
            "status": subprocess.CalledProcessError(
                returncode=128,
                cmd=["git", "status"],
                stderr="fatal: not a git repository\n",
            ),
        },
    )

    result = get_local_status(repo)

    assert "not a git repository" in result.error
    assert result.files == []


def test_get_local_status_git_not_installed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _make_repo(tmp_path)

    def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess:
        raise FileNotFoundError(2, "No such file", "git")

    monkeypatch.setattr(git_status.subprocess, "run", fake_run)

    result = get_local_status(repo)

    assert result.error == "git not installed"
    assert result.files == []


# ---------------------------------------------------------------------------
# status_char — single-character list indicator
# ---------------------------------------------------------------------------


def test_status_char_none_is_question_mark() -> None:
    assert status_char(None)[0] == "?"


def test_status_char_error_is_dash() -> None:
    char, _ = status_char(GitLocalStatus(error="not a git repository"))
    assert char == "-"


def test_status_char_clean_synced_is_tick() -> None:
    char, colour = status_char(GitLocalStatus(branch="main", upstream="origin/main"))
    assert (char, colour) == ("✓", "green")


def test_status_char_ahead_only() -> None:
    char, colour = status_char(
        GitLocalStatus(branch="main", upstream="origin/main", ahead=2)
    )
    assert (char, colour) == ("↑", "green")


def test_status_char_behind_only() -> None:
    char, colour = status_char(
        GitLocalStatus(branch="main", upstream="origin/main", behind=1)
    )
    assert (char, colour) == ("↓", "yellow")


def test_status_char_diverged() -> None:
    char, colour = status_char(
        GitLocalStatus(
            branch="main", upstream="origin/main", ahead=2, behind=1
        )
    )
    assert (char, colour) == ("⇅", "red")


def test_status_char_dirty_beats_ahead_behind() -> None:
    # Dirty working tree outranks ahead/behind in the priority order.
    char, colour = status_char(
        GitLocalStatus(
            branch="main",
            upstream="origin/main",
            ahead=5,
            behind=5,
            files=[GitFile(code=" M", path="foo.py")],
        )
    )
    assert (char, colour) == ("●", "yellow")


def test_status_char_conflict_beats_dirty() -> None:
    # Conflict markers beat plain dirty state.
    char, colour = status_char(
        GitLocalStatus(
            branch="main",
            files=[
                GitFile(code=" M", path="foo.py"),
                GitFile(code="UU", path="conflict.py"),
            ],
        )
    )
    assert (char, colour) == ("!", "red")


# ---------------------------------------------------------------------------
# Persistent cache helpers
# ---------------------------------------------------------------------------


def test_cache_round_trip(tmp_path: Path) -> None:
    cache = PersistentCache(tmp_path / "cache.pkl")
    status = GitLocalStatus(
        branch="main",
        upstream="origin/main",
        ahead=1,
        files=[GitFile(code=" M", path="x.py")],
    )

    assert get_cached_local_status(cache, "myrepo") is None

    cache_local_status(cache, "myrepo", status)
    loaded = get_cached_local_status(cache, "myrepo")

    assert loaded is not None
    assert loaded.branch == "main"
    assert loaded.ahead == 1
    assert [(f.code, f.path) for f in loaded.files] == [(" M", "x.py")]


def test_cache_persists_across_instances(tmp_path: Path) -> None:
    path = tmp_path / "cache.pkl"
    cache = PersistentCache(path)
    cache_local_status(
        cache, "repo-a", GitLocalStatus(branch="main", ahead=3)
    )

    reloaded = PersistentCache(path)
    loaded = get_cached_local_status(reloaded, "repo-a")

    assert loaded is not None
    assert loaded.ahead == 3


def test_cache_unrelated_key_is_none(tmp_path: Path) -> None:
    cache = PersistentCache(tmp_path / "cache.pkl")
    # Sanity: the key namespace is scoped by cache_key() so unrelated keys
    # don't accidentally return GitLocalStatus instances.
    cache.set("something:else", {"unrelated": True})
    assert get_cached_local_status(cache, "anything") is None
