"""Shared test fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from sman.config import Config, OrgConfig


@pytest.fixture(autouse=True)
def _isolate_xdg_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Redirect XDG_CACHE_HOME so tests don't touch the user's real cache dir."""
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "xdg-cache"))


@pytest.fixture
def tmp_config_path(tmp_path: Path) -> Path:
    return tmp_path / "config.toml"


@pytest.fixture
def sample_config() -> Config:
    return Config(
        default_org="test-org",
        cache_ttl_seconds=60,
        orgs=[
            OrgConfig(name="test-org", token="ghp_fake1", type="org"),
            OrgConfig(
                name="personal",
                token_env="SMAN_TEST_TOKEN",
                type="user",
            ),
        ],
    )
