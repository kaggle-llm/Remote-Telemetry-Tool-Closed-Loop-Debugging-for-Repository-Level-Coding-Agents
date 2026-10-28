"""Proxy configuration and the headers sent through a proxy."""

from __future__ import annotations

import base64
from collections.abc import Mapping
from dataclasses import dataclass

HOP_BY_HOP_HEADERS = frozenset(
    {"connection", "keep-alive", "proxy-authenticate", "proxy-authorization", "te",
     "trailer", "transfer-encoding", "upgrade"}
)


@dataclass(frozen=True)
class ProxyConfig:
    """Connection details of the proxy used for outgoing requests."""

    host: str
    port: int
    scheme: str = "http"
    username: str | None = None
    password: str | None = None

    def __post_init__(self) -> None:
        if not self.host:
            raise ValueError("host must not be empty")
        if not 1 <= self.port <= 65535:
            raise ValueError("port is out of range")
        if self.scheme not in ("http", "https"):
            raise ValueError("unsupported proxy scheme")

    @property
    def url(self) -> str:
        """URL of the proxy endpoint."""
        return f"{self.scheme}://{self.host}:{self.port}"

    def authorization_header(self) -> str | None:
        """Proxy authorization header built from the configured credentials."""
        if self.username is None:
            return None
        raw = f"{self.username}:{self.password or ''}".encode("utf-8")
        return "Basic " + base64.b64encode(raw).decode("ascii")


def build_proxy_config(host: str, port: int, *, scheme: str = "http",
                       username: str | None = None,
                       password: str | None = None) -> ProxyConfig:
    """Build the proxy configuration used by the network layer."""
    return ProxyConfig(host=host, port=port, scheme=scheme,
                       username=username, password=password)


def apply_proxy_headers(headers: Mapping[str, str],
                        config: ProxyConfig | None = None) -> dict[str, str]:
    """Return the headers of a request that travels through ``config``.

    Hop by hop headers belong to a single connection and are never
    forwarded to the server behind the proxy.
    """
    result = {name: value for name, value in headers.items()
              if name.lower() not in HOP_BY_HOP_HEADERS}
    if config is None:
        return result
    authorization = config.authorization_header()
    if authorization is not None:
        result["Proxy-Authorization"] = authorization
    return result
