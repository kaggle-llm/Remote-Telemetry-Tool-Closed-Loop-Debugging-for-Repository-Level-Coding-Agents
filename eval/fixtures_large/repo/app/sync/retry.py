"""Retry policy used when the synchronisation server reports a failure."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, TypeVar

T = TypeVar("T")


class SyncError(RuntimeError):
    """Base class for the failures reported by the synchronisation server."""


class TransientSyncError(SyncError):
    """Raised when the server asks the client to try again later."""


@dataclass(frozen=True)
class RetryPolicy:
    """How often and how quickly a failed operation is retried."""

    attempts: int = 3
    base_delay_ms: int = 25
    max_delay_ms: int = 1000

    def delay_ms(self, attempt: int) -> int:
        """Delay in milliseconds before the given one based attempt."""
        return min(self.base_delay_ms * (2 ** max(0, attempt - 1)), self.max_delay_ms)


class RetryRunner:
    """Runs a synchronisation operation and retries transient failures.

    An operation that is not protected by an idempotency key must never be
    replayed, because a replay can create a second copy of the same record
    on the server.
    """

    def __init__(
        self,
        policy: RetryPolicy | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._policy = policy if policy is not None else RetryPolicy()
        self._sleep = sleep

    @property
    def policy(self) -> RetryPolicy:
        """The retry policy in use."""
        return self._policy

    def run(self, operation: Callable[[], T], *, idempotency_key: str | None = None) -> T:
        """Run ``operation`` and retry it while the server reports transient errors."""
        last_error: SyncError | None = None
        for attempt in range(1, self._policy.attempts + 1):
            try:
                return operation()
            except TransientSyncError as error:
                last_error = error
                if attempt >= self._policy.attempts:
                    break
                self._sleep(self._policy.delay_ms(attempt) / 1000)
        raise last_error
