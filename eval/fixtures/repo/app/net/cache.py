"""Small in-memory cache for downloaded images."""

from __future__ import annotations

from collections import OrderedDict


class ImageCache:
    """Least recently used cache for image payloads."""

    def __init__(self, max_entries: int = 32) -> None:
        if max_entries < 1:
            raise ValueError("max_entries must be positive")
        self._max_entries = max_entries
        self._entries: OrderedDict[str, bytes] = OrderedDict()

    def __len__(self) -> int:
        return len(self._entries)

    @property
    def max_entries(self) -> int:
        """Maximum number of payloads kept in the cache."""
        return self._max_entries

    def get(self, key: str) -> bytes | None:
        """Return the payload stored under ``key`` when it is still cached."""
        payload = self._entries.get(key)
        if payload is None:
            return None
        self._entries.move_to_end(key)
        return payload

    def put(self, key: str, payload: bytes) -> None:
        """Store ``payload`` under ``key``, evicting the oldest entry."""
        if key in self._entries:
            self._entries.move_to_end(key)
        self._entries[key] = payload
        while len(self._entries) > self._max_entries:
            self._entries.popitem(last=False)

    def clear(self) -> None:
        """Drop every cached payload."""
        self._entries.clear()
