"""The monotonic clock used by the synchronisation worker."""

from __future__ import annotations

import time
from typing import Callable


class MonotonicClock:
    """A clock that never moves backwards.

    The synchronisation worker uses the clock to measure how long a
    retry has waited already and to decide when the backoff deadline of
    an attempt has passed.
    """

    def __init__(self, source: Callable[[], float] = time.monotonic) -> None:
        self._source = source
        self._last = 0.0

    def now(self) -> float:
        """Current time in seconds since an arbitrary fixed point."""
        value = self._source()
        if value < self._last:
            raise RuntimeError("the clock moved backwards")
        self._last = value
        return value

    def elapsed_ms(self, since: float) -> int:
        """Milliseconds that passed since the monotonic time ``since``."""
        elapsed = (self.now() - since) * 1000
        return max(0, int(elapsed))

    def deadline(self, budget_ms: int) -> float:
        """Monotonic time at which ``budget_ms`` milliseconds have passed."""
        if budget_ms <= 0:
            raise ValueError("budget_ms must be positive")
        return self.now() + budget_ms / 1000

    def expired(self, deadline: float) -> bool:
        """Whether the monotonic ``deadline`` has passed."""
        return self.now() >= deadline
