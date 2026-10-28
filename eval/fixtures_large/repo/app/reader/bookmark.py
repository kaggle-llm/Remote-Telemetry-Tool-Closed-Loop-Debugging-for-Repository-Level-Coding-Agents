"""Bookmarks that mark a passage inside a document."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Bookmark:
    """A marked position inside a document."""

    document_id: str
    page: int
    offset: int = 0
    label: str = ""

    def __post_init__(self) -> None:
        if self.page < 0:
            raise ValueError("page must not be negative")
        if self.offset < 0:
            raise ValueError("offset must not be negative")


def is_valid_page(page: int, page_count: int) -> bool:
    """Whether ``page`` still exists in a document of ``page_count`` pages.

    The pages of a document are numbered from zero, so the last page of
    the document is ``page_count - 1``.
    """
    return 0 <= page < page_count


class BookmarkStore:
    """Stores the bookmarks of every open document."""

    def __init__(self, max_bookmarks: int = 64) -> None:
        if max_bookmarks < 1:
            raise ValueError("max_bookmarks must be positive")
        self._max_bookmarks = max_bookmarks
        self._bookmarks: dict[str, list[Bookmark]] = {}

    def __len__(self) -> int:
        return sum(len(items) for items in self._bookmarks.values())

    @property
    def max_bookmarks(self) -> int:
        """Maximum number of bookmarks kept per document."""
        return self._max_bookmarks

    def add(self, bookmark: Bookmark) -> None:
        """Remember ``bookmark`` for the document it belongs to."""
        items = self._bookmarks.setdefault(bookmark.document_id, [])
        if bookmark not in items:
            items.append(bookmark)
        while len(items) > self._max_bookmarks:
            items.pop(0)

    def bookmarks(self, document_id: str) -> tuple[Bookmark, ...]:
        """The bookmarks stored for ``document_id``."""
        return tuple(self._bookmarks.get(document_id, ()))

    def restore(self, document_id: str, page: int, page_count: int) -> Bookmark | None:
        """Return the bookmark of ``document_id`` that points at ``page``.

        A bookmark whose page no longer exists after the document was
        laid out again is dropped instead of pointing at an empty page.
        """
        if not is_valid_page(page, page_count):
            return None
        for bookmark in self._bookmarks.get(document_id, ()):
            if bookmark.page == page:
                return bookmark
        return None
