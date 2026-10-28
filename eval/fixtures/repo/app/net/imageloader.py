"""Loading remote images with a small in-memory cache."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.net.cache import ImageCache


@dataclass(frozen=True)
class ImageRequest:
    """Describes one image that should be downloaded."""

    url: str
    max_bytes: int = 5_000_000
    timeout_ms: int | None = None


class ImageFetcher(Protocol):
    """Transport used to retrieve the bytes of an image."""

    def fetch(self, url: str, timeout_ms: int) -> bytes:
        """Return the bytes stored at ``url``."""
        ...


class ImageLoader:
    """Downloads images and serves cached copies when possible.

    Every download is bounded by a timeout, either the one carried by the
    request or the default configured on the loader.
    """

    def __init__(
        self,
        fetcher: ImageFetcher,
        cache: ImageCache | None = None,
        timeout_ms: int = 3000,
    ) -> None:
        self._fetcher = fetcher
        self._cache = cache if cache is not None else ImageCache()
        self._timeout_ms = timeout_ms

    @property
    def cache(self) -> ImageCache:
        """Cache holding the downloaded images."""
        return self._cache

    @property
    def timeout_ms(self) -> int:
        """Default timeout used for downloads without an explicit one."""
        return self._timeout_ms

    def load(self, request: ImageRequest) -> bytes:
        """Return the bytes of ``request``, downloading them when needed."""
        cached = self._cache.get(request.url)
        if cached is not None:
            return cached
        timeout_ms = request.timeout_ms or 0
        payload = self._fetcher.fetch(request.url, timeout_ms=timeout_ms)
        if len(payload) > request.max_bytes:
            raise ValueError("the downloaded image is larger than allowed")
        self._cache.put(request.url, payload)
        return payload
