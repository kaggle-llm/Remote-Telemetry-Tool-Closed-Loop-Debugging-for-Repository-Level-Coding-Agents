"""Queue of pending synchronisation jobs."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field


@dataclass
class SyncJob:
    """One unit of work waiting to be synchronised."""

    document_id: str
    kind: str
    payload: bytes = b""
    attempts: int = 0
    tags: list[str] = field(default_factory=list)


class SyncQueue:
    """First in first out queue of jobs waiting for the sync worker."""

    def __init__(self, max_jobs: int = 128) -> None:
        if max_jobs < 1:
            raise ValueError("max_jobs must be positive")
        self._max_jobs = max_jobs
        self._jobs: deque[SyncJob] = deque()

    def __len__(self) -> int:
        return len(self._jobs)

    @property
    def max_jobs(self) -> int:
        """Maximum number of jobs kept in the queue."""
        return self._max_jobs

    def push(self, job: SyncJob) -> bool:
        """Add ``job`` to the queue, returning ``False`` when the queue is full."""
        if len(self._jobs) >= self._max_jobs:
            return False
        self._jobs.append(job)
        return True

    def pop(self) -> SyncJob | None:
        """Remove and return the oldest job, or ``None`` when the queue is empty."""
        if not self._jobs:
            return None
        job = self._jobs.popleft()
        job.attempts += 1
        return job

    def pending(self, kind: str | None = None) -> list[SyncJob]:
        """Jobs still waiting, optionally filtered by kind."""
        jobs = list(self._jobs)
        if kind is None:
            return jobs
        return [job for job in jobs if job.kind == kind]
