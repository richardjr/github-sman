"""Tests for the GitHub client wrapper."""

from __future__ import annotations

import pytest

from sman.config import OrgConfig
from sman.github.client import GitHubClient


def test_from_config_no_token() -> None:
    org = OrgConfig(name="empty", token="", type="org")
    with pytest.raises(ValueError, match="No token configured"):
        GitHubClient.from_config(org)


def test_from_config_creates_client() -> None:
    org = OrgConfig(name="test", token="ghp_fake", type="org")
    client = GitHubClient.from_config(org, cache_ttl=120)
    assert client.name == "test"
    assert client.org_type == "org"
    assert client.cache is not None
    assert client.github is not None
    client.close()


def test_cache_ttl_propagated() -> None:
    org = OrgConfig(name="test", token="ghp_fake", type="org")
    client = GitHubClient.from_config(org, cache_ttl=42)
    assert client.cache._default_ttl == 42
    client.close()
