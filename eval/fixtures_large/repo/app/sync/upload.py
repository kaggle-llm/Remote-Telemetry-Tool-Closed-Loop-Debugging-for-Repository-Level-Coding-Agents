"""Chunked uploads of local documents to the synchronisation server."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class UploadProgress:
    """How much of an upload has reached the server."""

    uploaded_bytes: int
    total_bytes: int

    @property
    def fraction(self) -> float:
        """Fraction of the payload that has been uploaded."""
        if self.total_bytes <= 0:
            return 1.0
        return self.uploaded_bytes / self.total_bytes


class UploadTransport(Protocol):
    """Transport that accepts the chunks of an upload."""

    def send_chunk(self, document_id: str, chunk: bytes, *, idempotency_key: str) -> None:
        """Store one chunk of an upload under ``idempotency_key``."""
        ...


class Uploader:
    """Uploads a document in chunks and reports the progress.

    Every upload carries an idempotency key, so a chunk that is sent
    again after a transient failure is stored only once and a retry of a
    failed upload never creates a second copy of the document.
    """

    def __init__(self, transport: UploadTransport, *, chunk_size: int = 256_000) -> None:
        if chunk_size < 1:
            raise ValueError("chunk_size must be positive")
        self._transport = transport
        self._chunk_size = chunk_size

    @property
    def chunk_size(self) -> int:
        """Number of bytes sent in one chunk."""
        return self._chunk_size

    def idempotency_key(self, document_id: str, revision: int) -> str:
        """Key that identifies one upload of one revision of a document."""
        return f"upload-{document_id}-{revision}"

    def chunks(self, payload: bytes) -> list[bytes]:
        """Split ``payload`` into the chunks that are sent to the server."""
        return [
            payload[start:start + self._chunk_size]
            for start in range(0, len(payload), self._chunk_size)
        ]

    def upload(
        self,
        document_id: str,
        payload: bytes,
        *,
        revision: int = 0,
        on_progress: Callable[[UploadProgress], None] | None = None,
    ) -> UploadProgress:
        """Upload ``payload`` and report the final progress.

        The same idempotency key is used for every chunk of one upload,
        so the server can recognise a chunk that arrives twice and keep
        a single copy of the document.
        """
        key = self.idempotency_key(document_id, revision)
        total_bytes = len(payload)
        uploaded_bytes = 0
        for chunk in self.chunks(payload):
            self._transport.send_chunk(document_id, chunk, idempotency_key=key)
            uploaded_bytes += len(chunk)
            if on_progress is not None:
                on_progress(UploadProgress(uploaded_bytes=uploaded_bytes, total_bytes=total_bytes))
        return UploadProgress(uploaded_bytes=uploaded_bytes, total_bytes=total_bytes)
