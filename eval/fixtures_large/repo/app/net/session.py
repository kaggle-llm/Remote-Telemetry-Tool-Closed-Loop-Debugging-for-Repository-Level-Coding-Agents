"""Lifecycle of the HTTP sessions used to reach the content servers."""

from __future__ import annotations

from typing import Protocol


class SessionError(RuntimeError):
    """Raised when an HTTP session cannot complete a request."""


class RequestTimeoutError(SessionError):
    """Raised when a request runs into the timeout of its session."""


class Transport(Protocol):
    """Transport that performs the requests of a session."""

    def request(self, method: str, url: str, *, headers: dict[str, str], timeout_ms: int) -> bytes:
        """Perform one request and return the payload of the answer."""
        ...


class HttpSession:
    """A reusable HTTP session with an explicit timeout.

    Every request of the session is bounded by ``timeout_ms``; the
    timeout is never left out, so a slow connection can never keep a
    request pending forever.
    """

    def __init__(self, transport: Transport, timeout_ms: int = 5000) -> None:
        if timeout_ms <= 0:
            raise ValueError("timeout_ms must be positive")
        self._transport = transport
        self._timeout_ms = timeout_ms
        self._closed = False

    @property
    def timeout_ms(self) -> int:
        """Timeout in milliseconds used for every request of the session."""
        return self._timeout_ms

    @property
    def is_closed(self) -> bool:
        """Whether the session has been closed."""
        return self._closed

    def request(self, method: str, url: str, *, headers: dict[str, str] | None = None,
                timeout_ms: int | None = None) -> bytes:
        """Perform a request that is bounded by a timeout.

        The timeout of the request wins over the timeout of the session
        and is always handed to the transport as a positive number of
        milliseconds.
        """
        if self._closed:
            raise SessionError("the session is closed")
        budget = self._timeout_ms if timeout_ms is None else timeout_ms
        if budget <= 0:
            raise RequestTimeoutError("a request needs a positive timeout")
        return self._transport.request(
            method,
            url,
            headers=dict(headers or {}),
            timeout_ms=budget,
        )

    def get(self, url: str, *, headers: dict[str, str] | None = None) -> bytes:
        """Perform a GET request bounded by the timeout of the session."""
        return self.request("GET", url, headers=headers)

    def close(self) -> None:
        """Close the session and refuse every later request."""
        self._closed = True
