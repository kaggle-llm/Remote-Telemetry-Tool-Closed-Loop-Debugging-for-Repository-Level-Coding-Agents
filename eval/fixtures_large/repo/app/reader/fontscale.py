"""Dynamic font scaling and the re-layout it triggers."""

from __future__ import annotations

from dataclasses import dataclass

from app.reader.pagination import Page, Paginator

MIN_SCALE = 0.8
MAX_SCALE = 2.0
BASE_PAGE_SIZE = 1200


@dataclass(frozen=True)
class FontScale:
    """The scale factor applied to the text of the reader."""

    factor: float = 1.0

    def __post_init__(self) -> None:
        if not MIN_SCALE <= self.factor <= MAX_SCALE:
            raise ValueError("the scale factor is out of range")

    @property
    def page_size(self) -> int:
        """Number of characters that fit on a page at this scale."""
        return max(1, int(BASE_PAGE_SIZE / self.factor))


class FontScaler:
    """Keeps the font scale of the reader and re-lays out the text.

    A larger font produces shorter pages, so the number of pages of a
    document changes whenever the reader changes the font size or the
    screen size.
    """

    def __init__(self, scale: float = 1.0) -> None:
        self._scale = FontScale(factor=scale)

    @property
    def scale(self) -> FontScale:
        """The scale factor currently applied to the text."""
        return self._scale

    def set_scale(self, factor: float) -> FontScale:
        """Apply ``factor`` and return the scale that is now in use."""
        self._scale = FontScale(factor=min(MAX_SCALE, max(MIN_SCALE, factor)))
        return self._scale

    def increase(self, step: float = 0.1) -> FontScale:
        """Make the text of the reader larger."""
        return self.set_scale(self._scale.factor + step)

    def decrease(self, step: float = 0.1) -> FontScale:
        """Make the text of the reader smaller."""
        return self.set_scale(self._scale.factor - step)

    def relayout(self, text: str) -> list[Page]:
        """Lay out ``text`` again with the current font scale.

        The pages of the result replace the pages of the previous
        layout, so every stored position has to be checked against the
        new page count.
        """
        paginator = Paginator(page_size=self._scale.page_size)
        return paginator.pages(text)
