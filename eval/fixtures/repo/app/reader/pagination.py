"""Splitting documents into fixed size pages."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Page:
    """One page of a paginated document."""

    index: int
    start: int
    end: int

    @property
    def length(self) -> int:
        """Number of characters contained in the page."""
        return self.end - self.start


class Paginator:
    """Splits text into pages of a fixed character budget."""

    def __init__(self, page_size: int = 1200) -> None:
        if page_size < 1:
            raise ValueError("page_size must be positive")
        self._page_size = page_size

    @property
    def page_size(self) -> int:
        """Maximum number of characters per page."""
        return self._page_size

    def page_count(self, text: str) -> int:
        """Number of pages needed to display ``text``."""
        if not text:
            return 0
        return (len(text) + self._page_size - 1) // self._page_size

    def pages(self, text: str) -> list[Page]:
        """Split ``text`` into pages of at most ``page_size`` characters."""
        pages: list[Page] = []
        for index, start in enumerate(range(0, len(text), self._page_size)):
            end = min(start + self._page_size, len(text))
            pages.append(Page(index=index, start=start, end=end))
        return pages

    def page_at(self, text: str, page: int) -> Page | None:
        """Return the page at ``page`` or ``None`` when there is no such page."""
        pages = self.pages(text)
        if page < 0 or page >= len(pages):
            return None
        return pages[page]
