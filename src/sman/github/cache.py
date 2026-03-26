"""Simple in-memory TTL cache for GitHub API responses."""

from __future__ import annotations

import time
from typing import Any


class Cache:
    """Dictionary-based cache with per-entry TTL expiration."""

    def __init__(self, default_ttl: int = 300) -> None:
        self._default_ttl = default_ttl
        self._store: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Any | None:
        """Get a value if it exists and hasn't expired."""
        entry = self._store.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if time.monotonic() > expires_at:
            del self._store[key]
            return None
        return value

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Store a value with TTL (seconds). Uses default_ttl if not specified."""
        ttl = ttl if ttl is not None else self._default_ttl
        self._store[key] = (time.monotonic() + ttl, value)

    def invalidate(self, key: str) -> None:
        """Remove a specific entry."""
        self._store.pop(key, None)

    def invalidate_prefix(self, prefix: str) -> None:
        """Remove all entries whose keys start with prefix."""
        to_remove = [k for k in self._store if k.startswith(prefix)]
        for k in to_remove:
            del self._store[k]

    def clear(self) -> None:
        """Remove all entries."""
        self._store.clear()
