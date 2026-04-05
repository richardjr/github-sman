"""Helpers for working with locally cloned repositories.

Kept separate from widgets/screens so they can be unit-tested and reused
without pulling Textual into the import graph.
"""

from __future__ import annotations

import shlex
import subprocess
from collections.abc import Sequence
from pathlib import Path

CLAUDE_MD_NAMES = ("CLAUDE.md", "claude.md")
DEFAULT_TERMINAL_TEMPLATE = "xdg-terminal-exec --dir={cwd} -- {cmd}"


def has_claude_md(repo_path: Path) -> bool:
    """Return True if repo_path contains a CLAUDE.md (or claude.md) file."""
    if not repo_path.is_dir():
        return False
    return any((repo_path / name).is_file() for name in CLAUDE_MD_NAMES)


def launch_terminal(
    cwd: Path, command: str | Sequence[str], template: str = ""
) -> None:
    """Spawn a detached terminal running ``command`` in ``cwd``.

    ``command`` may be a single program name or a sequence of argv tokens
    (e.g. ``["nvim", "."]``) — each element is quoted independently so it
    survives the template round-trip as a distinct argv element.

    ``template`` is a command string containing ``{cwd}`` and ``{cmd}``
    placeholders. When empty, ``DEFAULT_TERMINAL_TEMPLATE`` is used, which
    defers to ``xdg-terminal-exec`` so the user's XDG/omarchy default
    terminal is picked up automatically.
    """
    parts = [command] if isinstance(command, str) else list(command)
    cmd_rendered = " ".join(shlex.quote(p) for p in parts)
    tmpl = template or DEFAULT_TERMINAL_TEMPLATE
    rendered = tmpl.format(cwd=shlex.quote(str(cwd)), cmd=cmd_rendered)
    argv = shlex.split(rendered)
    subprocess.Popen(
        argv,
        cwd=str(cwd),
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
