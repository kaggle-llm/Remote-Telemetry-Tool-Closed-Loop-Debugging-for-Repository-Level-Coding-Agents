"""The annotation toolbar that appears above a selected passage."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from app.ui.palette import HighlightPalette


@dataclass(frozen=True)
class ToolbarAction:
    """One button offered by the annotation toolbar."""

    identifier: str
    label: str
    handler: Callable[[], None]
    enabled: bool = True

    def trigger(self) -> None:
        """Run the action when the button is enabled."""
        if not self.enabled:
            return
        self.handler()


def build_toolbar_actions(
    palette: HighlightPalette,
    *,
    on_copy: Callable[[], None] | None = None,
    on_note: Callable[[], None] | None = None,
) -> tuple[ToolbarAction, ...]:
    """Build the buttons of the annotation toolbar.

    The colour button owns the highlight palette and presents the colour
    swatches of that palette. The palette keeps the presentation context
    of the view that created it, so the toolbar opens it without
    repeating the context.
    """
    def open_colour_palette() -> None:
        palette.open_palette()

    actions: list[ToolbarAction] = [
        ToolbarAction(identifier="colour", label="Colour", handler=open_colour_palette),
        ToolbarAction(identifier="highlight", label="Highlight", handler=open_colour_palette),
    ]
    if on_copy is not None:
        actions.append(ToolbarAction(identifier="copy", label="Copy", handler=on_copy))
    if on_note is not None:
        actions.append(ToolbarAction(identifier="note", label="Note", handler=on_note))
    return tuple(actions)


class AnnotationToolbar:
    """The bar of buttons shown above a selected passage."""

    def __init__(self, palette: HighlightPalette) -> None:
        self._actions = build_toolbar_actions(palette)
        self._last_triggered: str | None = None

    @property
    def actions(self) -> tuple[ToolbarAction, ...]:
        """The buttons of the toolbar in display order."""
        return self._actions

    @property
    def last_triggered(self) -> str | None:
        """Identifier of the button that was used last."""
        return self._last_triggered

    def trigger(self, identifier: str) -> bool:
        """Use the button called ``identifier``."""
        for action in self._actions:
            if action.identifier == identifier:
                self._last_triggered = identifier
                action.trigger()
                return True
        return False
