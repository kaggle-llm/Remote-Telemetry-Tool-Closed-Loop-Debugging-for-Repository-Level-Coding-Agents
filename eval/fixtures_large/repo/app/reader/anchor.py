"""Reading anchors used to restore the last read position."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReadingAnchor:
    """Position of the reader inside a paginated document."""

    page: int
    offset: int = 0
    revision: int = 0


class AnchorStore:
    """Stores the most recent reading anchor of every open document."""

    def __init__(self, max_documents: int = 16) -> None:
        if max_documents < 1:
            raise ValueError("max_documents must be positive")
        self._max_documents = max_documents
        self._anchors: dict[str, ReadingAnchor] = {}

    @property
    def max_documents(self) -> int:
        """Maximum number of documents kept in the store."""
        return self._max_documents

    def save(self, document_id: str, anchor: ReadingAnchor) -> None:
        """Remember ``anchor`` as the last position of ``document_id``."""
        if document_id not in self._anchors and len(self._anchors) >= self._max_documents:
            oldest = next(iter(self._anchors))
            del self._anchors[oldest]
        self._anchors[document_id] = anchor

    def load(self, document_id: str) -> ReadingAnchor | None:
        """Return the stored anchor of ``document_id`` without validating it."""
        return self._anchors.get(document_id)

    def restore(self, document_id: str, page_count: int) -> ReadingAnchor | None:
        """Return the anchor of ``document_id`` when it still fits the document.

        A document is paginated into ``page_count`` pages numbered from
        zero, so an anchor that points outside that range is no longer
        valid and is dropped.
        """
        anchor = self._anchors.get(document_id)
        if anchor is None:
            return None
        if anchor.page > page_count:
            return None
        return anchor
