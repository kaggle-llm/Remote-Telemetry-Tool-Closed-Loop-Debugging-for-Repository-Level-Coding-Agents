"""Highlight colour palette shown by the annotation toolbar."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class PaletteColor:
    """One colour offered by the highlight palette."""

    name: str
    hex_value: str


@dataclass(frozen=True)
class PresentationContext:
    """Identifies the surface a palette is presented on."""

    view: str
    session_id: str


DEFAULT_COLORS: tuple[PaletteColor, ...] = (
    PaletteColor(name="yellow", hex_value="ffd60a"),
    PaletteColor(name="green", hex_value="34c759"),
    PaletteColor(name="blue", hex_value="0a84ff"),
    PaletteColor(name="red", hex_value="ff453a"),
)


class HighlightPalette:
    """Palette of highlight colours offered by the annotation toolbar.

    A palette is created by the view that owns it and keeps the presentation
    context of that view, so the toolbar can open the palette without
    repeating the context.
    """

    def __init__(
        self,
        context: PresentationContext,
        colors: Iterable[PaletteColor] | None = None,
    ) -> None:
        self._context = context
        self._colors = tuple(colors) if colors is not None else DEFAULT_COLORS
        self._open = False

    @property
    def colors(self) -> tuple[PaletteColor, ...]:
        """Colours offered by the palette, in display order."""
        return self._colors

    @property
    def current_context(self) -> PresentationContext:
        """Context the palette is currently bound to."""
        return self._context

    @property
    def is_open(self) -> bool:
        """Whether the palette is currently presented."""
        return self._open

    def open_palette(self, context: PresentationContext | None = None) -> bool:
        """Present the palette and report whether it was presented."""
        if context is None:
            return False
        self._open = True
        self._context = context
        return True

    def close_palette(self) -> None:
        """Dismiss the palette."""
        self._open = False
