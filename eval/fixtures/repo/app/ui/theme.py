"""Theme definitions and the dark mode switch."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class Theme:
    """Colour and spacing values used by the interface."""

    name: str
    background: str
    foreground: str
    accent: str
    spacing: int = 8


LIGHT_THEME = Theme(
    name="light",
    background="ffffff",
    foreground="111111",
    accent="0a84ff",
)

DARK_THEME = Theme(
    name="dark",
    background="1c1c1e",
    foreground="f5f5f7",
    accent="64d2ff",
)


class ThemeManager:
    """Keeps the active theme and notifies listeners about every change."""

    def __init__(self, theme: Theme = LIGHT_THEME) -> None:
        self._theme = theme
        self._listeners: list[Callable[[Theme], None]] = []

    @property
    def active(self) -> Theme:
        """The theme currently applied to the interface."""
        return self._theme

    def on_change(self, listener: Callable[[Theme], None]) -> None:
        """Register a callback invoked after every theme change."""
        self._listeners.append(listener)

    def switch(self, theme: Theme) -> None:
        """Apply ``theme`` and notify the registered listeners."""
        if theme.name == self._theme.name:
            return
        self._theme = theme
        for listener in self._listeners:
            listener(theme)

    def toggle(self) -> Theme:
        """Switch between the light and the dark theme."""
        self.switch(DARK_THEME if self._theme.name == LIGHT_THEME.name else LIGHT_THEME)
        return self._theme
