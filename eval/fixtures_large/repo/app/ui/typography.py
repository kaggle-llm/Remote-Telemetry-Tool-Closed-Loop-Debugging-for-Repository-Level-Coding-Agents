"""Font metrics of the text that is currently selected."""

from __future__ import annotations

import math
from dataclasses import dataclass

from app.ui.selection import Selection


@dataclass(frozen=True)
class FontMetrics:
    """Size of the characters of a document."""

    size_pt: float
    line_height_pt: float
    average_char_width_pt: float

    def __post_init__(self) -> None:
        if self.size_pt <= 0:
            raise ValueError("size_pt must be positive")
        if self.line_height_pt <= 0:
            raise ValueError("line_height_pt must be positive")
        if self.average_char_width_pt <= 0:
            raise ValueError("average_char_width_pt must be positive")

    def width_of(self, character_count: int) -> float:
        """Width in points of ``character_count`` characters."""
        if character_count < 0:
            raise ValueError("character_count must not be negative")
        return character_count * self.average_char_width_pt


@dataclass(frozen=True)
class SelectionMetrics:
    """Metrics of one measured selection."""

    selection: Selection
    metrics: FontMetrics
    width_pt: float
    height_pt: float
    line_count: int


DEFAULT_METRICS = FontMetrics(size_pt=15.0, line_height_pt=20.0, average_char_width_pt=7.5)


def measure_selection(
    selection: Selection,
    metrics: FontMetrics = DEFAULT_METRICS,
    *,
    available_width_pt: float = 320.0,
) -> SelectionMetrics:
    """Measure the passage covered by ``selection``.

    The measurement tells the annotation toolbar how much room the
    selected passage needs, so the bar with the colour button can be
    placed above it.
    """
    if available_width_pt <= 0:
        raise ValueError("available_width_pt must be positive")
    width_pt = metrics.width_of(selection.length)
    line_count = max(1, math.ceil(width_pt / available_width_pt))
    return SelectionMetrics(
        selection=selection,
        metrics=metrics,
        width_pt=width_pt,
        height_pt=line_count * metrics.line_height_pt,
        line_count=line_count,
    )


def has_measurable_selection(selection: Selection | None) -> bool:
    """Whether ``selection`` holds a passage that can be measured."""
    return selection is not None and selection.length > 0
