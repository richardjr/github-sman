"""Tests for PersistentCache."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from sman.github.persistent_cache import (
    PersistentCache,
    default_cache_dir,
)


def test_get_missing_key_returns_none(tmp_path: Path) -> None:
    cache = PersistentCache(tmp_path / "cache.pkl")
    assert cache.get("nope") is None


def test_set_and_get_round_trip(tmp_path: Path) -> None:
    cache = PersistentCache(tmp_path / "cache.pkl")
    cache.set("key", {"value": 42})
    result = cache.get("key")
    assert result is not None
    value, cached_at = result
    assert value == {"value": 42}
    # cached_at should be close to now
    assert abs(cached_at - time.time()) < 5


def test_persists_across_instances(tmp_path: Path) -> None:
    path = tmp_path / "cache.pkl"
    a = PersistentCache(path)
    a.set("key", [1, 2, 3])

    b = PersistentCache(path)
    result = b.get("key")
    assert result is not None
    value, _ = result
    assert value == [1, 2, 3]


def test_invalidate_removes_entry(tmp_path: Path) -> None:
    cache = PersistentCache(tmp_path / "cache.pkl")
    cache.set("a", 1)
    cache.set("b", 2)
    cache.invalidate("a")
    assert cache.get("a") is None
    assert cache.get("b") is not None


def test_invalidate_prefix_removes_matching(tmp_path: Path) -> None:
    cache = PersistentCache(tmp_path / "cache.pkl")
    cache.set("repos:org1:updated", ["a"])
    cache.set("repos:org1:stars", ["b"])
    cache.set("other:org1", ["c"])

    cache.invalidate_prefix("repos:org1")

    assert cache.get("repos:org1:updated") is None
    assert cache.get("repos:org1:stars") is None
    assert cache.get("other:org1") is not None


def test_invalidate_prefix_persists(tmp_path: Path) -> None:
    path = tmp_path / "cache.pkl"
    cache = PersistentCache(path)
    cache.set("repos:a", 1)
    cache.set("repos:b", 2)
    cache.invalidate_prefix("repos:")

    reloaded = PersistentCache(path)
    assert reloaded.get("repos:a") is None
    assert reloaded.get("repos:b") is None


def test_corrupt_file_is_treated_as_empty(tmp_path: Path) -> None:
    path = tmp_path / "cache.pkl"
    path.write_bytes(b"not a pickle at all")
    cache = PersistentCache(path)
    assert cache.get("anything") is None
    # Should still work after recovery
    cache.set("key", "value")
    assert cache.get("key") is not None


def test_clear_empties_cache(tmp_path: Path) -> None:
    path = tmp_path / "cache.pkl"
    cache = PersistentCache(path)
    cache.set("a", 1)
    cache.set("b", 2)
    cache.clear()
    assert cache.get("a") is None
    assert cache.get("b") is None

    reloaded = PersistentCache(path)
    assert reloaded.get("a") is None


def test_default_cache_dir_honors_xdg(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "xdg"))
    assert default_cache_dir() == tmp_path / "xdg" / "sman"


def test_default_cache_dir_falls_back_to_home(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    assert default_cache_dir() == tmp_path / ".cache" / "sman"
