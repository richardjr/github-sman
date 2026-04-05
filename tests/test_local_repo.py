"""Tests for local_repo helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from sman import local_repo
from sman.local_repo import (
    DEFAULT_TERMINAL_TEMPLATE,
    has_claude_md,
    launch_terminal,
)


def test_has_claude_md_true_for_uppercase(tmp_path: Path) -> None:
    (tmp_path / "CLAUDE.md").write_text("# hi")
    assert has_claude_md(tmp_path) is True


def test_has_claude_md_true_for_lowercase(tmp_path: Path) -> None:
    (tmp_path / "claude.md").write_text("# hi")
    assert has_claude_md(tmp_path) is True


def test_has_claude_md_false_when_absent(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# hi")
    assert has_claude_md(tmp_path) is False


def test_has_claude_md_false_for_non_directory(tmp_path: Path) -> None:
    missing = tmp_path / "nope"
    assert has_claude_md(missing) is False


def test_has_claude_md_false_when_path_is_a_file(tmp_path: Path) -> None:
    f = tmp_path / "file"
    f.write_text("x")
    assert has_claude_md(f) is False


class _FakePopen:
    """Captures the arguments passed to subprocess.Popen."""

    instances: list[_FakePopen] = []

    def __init__(self, argv, **kwargs):
        self.argv = argv
        self.kwargs = kwargs
        _FakePopen.instances.append(self)


@pytest.fixture(autouse=True)
def _reset_fake_popen():
    _FakePopen.instances.clear()
    yield
    _FakePopen.instances.clear()


def test_launch_terminal_default_template(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(local_repo.subprocess, "Popen", _FakePopen)

    launch_terminal(tmp_path, "claude")

    assert len(_FakePopen.instances) == 1
    call = _FakePopen.instances[0]
    # Default template uses xdg-terminal-exec
    assert call.argv[0] == "xdg-terminal-exec"
    assert f"--dir={tmp_path}" in call.argv
    assert "claude" in call.argv
    assert call.kwargs["cwd"] == str(tmp_path)
    assert call.kwargs["start_new_session"] is True


def test_launch_terminal_uses_override_template(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(local_repo.subprocess, "Popen", _FakePopen)
    template = "kitty --working-directory={cwd} -- {cmd}"

    launch_terminal(tmp_path, "claude", template)

    call = _FakePopen.instances[0]
    assert call.argv[0] == "kitty"
    assert f"--working-directory={tmp_path}" in call.argv
    assert call.argv[-1] == "claude"


def test_launch_terminal_accepts_argv_sequence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Passing a list keeps each element as a distinct argv token."""
    monkeypatch.setattr(local_repo.subprocess, "Popen", _FakePopen)

    launch_terminal(tmp_path, ["nvim", "."])

    call = _FakePopen.instances[0]
    # "nvim" and "." must survive as separate trailing tokens, not a single
    # "nvim ." string that the terminal would treat as one binary name.
    assert call.argv[-2:] == ["nvim", "."]


def test_launch_terminal_quotes_paths_with_spaces(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(local_repo.subprocess, "Popen", _FakePopen)
    spaced = tmp_path / "dir with space"
    spaced.mkdir()

    launch_terminal(spaced, "claude")

    call = _FakePopen.instances[0]
    # After shlex round-trip the argv should contain the literal path intact
    assert any(str(spaced) in part for part in call.argv)
    assert call.kwargs["cwd"] == str(spaced)


def test_default_template_constant() -> None:
    # Sanity: default template has both required placeholders
    assert "{cwd}" in DEFAULT_TERMINAL_TEMPLATE
    assert "{cmd}" in DEFAULT_TERMINAL_TEMPLATE
