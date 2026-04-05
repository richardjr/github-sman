"""Disk-backed cache that survives process restarts.

Unlike the in-memory :class:`~sman.github.cache.Cache`, this cache does not
expire entries automatically. Values live forever until explicitly
invalidated. Each entry records the wall-clock time it was cached so the UI
can show a "last updated X ago" indicator.

Serialization uses pickle. Deserialization failures (corrupt file,
incompatible dataclass schema after a refactor, etc.) are treated as a
cache miss — the cache starts empty rather than raising.
"""

from __future__ import annotations

import os
import pickle
import time
from pathlib import Path
from typing import Any


def default_cache_dir() -> Path:
    """Return the XDG cache directory for sman."""
    xdg = os.environ.get("XDG_CACHE_HOME")
    base = Path(xdg) if xdg else Path.home() / ".cache"
    return base / "sman"


class PersistentCache:
    """Pickle-backed cache with wall-clock timestamps and no auto-expiry."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._store: dict[str, tuple[float, Any]] = {}
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            with open(self._path, "rb") as f:
                data = pickle.load(f)
            if isinstance(data, dict):
                self._store = data
        except Exception:
            # Corrupt, truncated, or schema-incompatible — start fresh.
            self._store = {}

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(self._path.suffix + ".tmp")
        with open(tmp, "wb") as f:
            pickle.dump(self._store, f)
        tmp.replace(self._path)

    def get(self, key: str) -> tuple[Any, float] | None:
        """Return (value, cached_at_unix_ts) or None if the key is absent."""
        entry = self._store.get(key)
        if entry is None:
            return None
        cached_at, value = entry
        return value, cached_at

    def set(self, key: str, value: Any) -> None:
        """Store ``value`` under ``key`` with the current wall-clock time."""
        self._store[key] = (time.time(), value)
        self._save()

    def invalidate(self, key: str) -> None:
        """Remove a specific entry. No-op if the key is absent."""
        if self._store.pop(key, None) is not None:
            self._save()

    def invalidate_prefix(self, prefix: str) -> None:
        """Remove all entries whose keys start with ``prefix``."""
        to_remove = [k for k in self._store if k.startswith(prefix)]
        if not to_remove:
            return
        for k in to_remove:
            del self._store[k]
        self._save()

    def clear(self) -> None:
        """Remove all entries."""
        if not self._store:
            return
        self._store.clear()
        self._save()
