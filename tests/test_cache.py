"""Tests for the TTL cache."""

from __future__ import annotations

import time

from sman.github.cache import Cache


def test_set_and_get() -> None:
    cache = Cache(default_ttl=60)
    cache.set("key1", "value1")
    assert cache.get("key1") == "value1"


def test_get_missing() -> None:
    cache = Cache()
    assert cache.get("nonexistent") is None


def test_expiration() -> None:
    cache = Cache(default_ttl=1)
    cache.set("key", "val", ttl=0)
    # TTL=0 means expires immediately after monotonic advances
    time.sleep(0.01)
    assert cache.get("key") is None


def test_custom_ttl() -> None:
    cache = Cache(default_ttl=0)
    cache.set("key", "val", ttl=60)
    assert cache.get("key") == "val"


def test_invalidate() -> None:
    cache = Cache()
    cache.set("key", "val")
    cache.invalidate("key")
    assert cache.get("key") is None


def test_invalidate_prefix() -> None:
    cache = Cache()
    cache.set("repos:org1:a", 1)
    cache.set("repos:org1:b", 2)
    cache.set("repos:org2:c", 3)
    cache.invalidate_prefix("repos:org1")
    assert cache.get("repos:org1:a") is None
    assert cache.get("repos:org1:b") is None
    assert cache.get("repos:org2:c") == 3


def test_clear() -> None:
    cache = Cache()
    cache.set("a", 1)
    cache.set("b", 2)
    cache.clear()
    assert cache.get("a") is None
    assert cache.get("b") is None
