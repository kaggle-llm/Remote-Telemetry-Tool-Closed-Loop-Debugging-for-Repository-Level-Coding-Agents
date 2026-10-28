"""Selection helpers shared by the annotation toolbar."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Selection:
    """A range of characters selected inside a document."""

    start: int
    end: int

    def __post_init__(self) -> None:
        if self.start < 0 or self.end < self.start:
            raise ValueError("invalid selection range")

    @property
    def length(self) -> int:
        """Number of characters covered by the selection."""
        return self.end - self.start

    def overlaps(self, other: Selection) -> bool:
        """Whether two selections share at least one character."""
        return self.start < other.end and other.start < self.end


class SelectionTracker:
    """Remembers the selection that is currently active in a document."""

    def __init__(self) -> None:
        self._selection: Selection | None = None

    @property
    def current(self) -> Selection | None:
        """The active selection, if there is one."""
        return self._selection

    def begin(self, start: int) -> None:
        """Start a new selection at ``start``."""
        self._selection = Selection(start=start, end=start)

    def extend_to(self, end: int) -> None:
        """Extend the active selection up to ``end``."""
        if self._selection is None:
            raise RuntimeError("there is no active selection")
        self._selection = Selection(start=self._selection.start, end=end)

    def clear(self) -> None:
        """Drop the active selection."""
        self._selection = None
