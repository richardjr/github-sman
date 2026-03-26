"""Tests for the config module."""

from __future__ import annotations

import os
from pathlib import Path

from sman.config import Config, OrgConfig


def test_load_missing_file(tmp_path: Path) -> None:
    config = Config.load(tmp_path / "nonexistent.toml")
    assert config.orgs == []
    assert config.default_org == ""


def test_save_and_load(tmp_config_path: Path, sample_config: Config) -> None:
    sample_config.save(tmp_config_path)
    assert tmp_config_path.exists()

    loaded = Config.load(tmp_config_path)
    assert loaded.default_org == "test-org"
    assert loaded.cache_ttl_seconds == 60
    assert len(loaded.orgs) == 2
    assert loaded.orgs[0].name == "test-org"
    assert loaded.orgs[0].token == "ghp_fake1"
    assert loaded.orgs[1].token_env == "SMAN_TEST_TOKEN"


def test_file_permissions(tmp_config_path: Path, sample_config: Config) -> None:
    sample_config.save(tmp_config_path)
    mode = tmp_config_path.stat().st_mode & 0o777
    assert mode == 0o600


def test_get_org(sample_config: Config) -> None:
    org = sample_config.get_org("test-org")
    assert org is not None
    assert org.type == "org"
    assert sample_config.get_org("nonexistent") is None


def test_get_default_org(sample_config: Config) -> None:
    default = sample_config.get_default_org()
    assert default is not None
    assert default.name == "test-org"


def test_get_default_org_fallback() -> None:
    config = Config(orgs=[OrgConfig(name="fallback", token="t")])
    assert config.get_default_org().name == "fallback"


def test_add_org(sample_config: Config) -> None:
    new_org = OrgConfig(name="new-org", token="ghp_new", type="org")
    sample_config.add_org(new_org)
    assert len(sample_config.orgs) == 3
    assert sample_config.get_org("new-org") is not None


def test_add_org_updates_existing(sample_config: Config) -> None:
    updated = OrgConfig(name="test-org", token="ghp_updated", type="org")
    sample_config.add_org(updated)
    assert len(sample_config.orgs) == 2
    assert sample_config.get_org("test-org").token == "ghp_updated"


def test_remove_org(sample_config: Config) -> None:
    assert sample_config.remove_org("personal") is True
    assert len(sample_config.orgs) == 1
    assert sample_config.get_org("personal") is None


def test_remove_default_org_updates_default(sample_config: Config) -> None:
    sample_config.remove_org("test-org")
    assert sample_config.default_org == "personal"


def test_remove_nonexistent_org(sample_config: Config) -> None:
    assert sample_config.remove_org("nope") is False


def test_resolve_token_from_env() -> None:
    org = OrgConfig(name="env-org", token_env="SMAN_TEST_VAR")
    os.environ["SMAN_TEST_VAR"] = "ghp_from_env"
    try:
        assert org.resolve_token() == "ghp_from_env"
    finally:
        del os.environ["SMAN_TEST_VAR"]


def test_resolve_token_fallback_to_direct() -> None:
    org = OrgConfig(name="direct-org", token="ghp_direct")
    assert org.resolve_token() == "ghp_direct"
