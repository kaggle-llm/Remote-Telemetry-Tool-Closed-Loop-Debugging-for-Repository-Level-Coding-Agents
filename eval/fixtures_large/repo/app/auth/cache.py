"""In-memory cache for authentication results."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class Credential:
    """An access token issued for a particular scope."""

    token: str
    scope: str


@dataclass(frozen=True)
class _Entry:
    credential: Credential
    stored_at: float


class CredentialCache:
    """Caches credentials for a short while to avoid repeated logins.

    A cached credential stays valid for ``ttl_ms`` milliseconds; once that
    window has passed the entry is dropped and the caller has to refresh.
    """

    def __init__(
        self,
        ttl_ms: int = 300_000,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if ttl_ms <= 0:
            raise ValueError("ttl_ms must be positive")
        self._ttl_ms = ttl_ms
        self._clock = clock
        self._entries: dict[str, _Entry] = {}

    @property
    def ttl_ms(self) -> int:
        """Lifetime of a cached credential in milliseconds."""
        return self._ttl_ms

    def __len__(self) -> int:
        return len(self._entries)

    def get(self, scope: str) -> Credential | None:
        """Return the cached credential of ``scope`` when it is still valid."""
        entry = self._entries.get(scope)
        if entry is None:
            return None
        return entry.credential

    def put(self, scope: str, credential: Credential) -> None:
        """Store ``credential`` for ``scope`` and restart its lifetime."""
        self._entries[scope] = _Entry(credential=credential, stored_at=self._clock())

    def invalidate(self, scope: str) -> None:
        """Remove the cached credential of ``scope``."""
        self._entries.pop(scope, None)
