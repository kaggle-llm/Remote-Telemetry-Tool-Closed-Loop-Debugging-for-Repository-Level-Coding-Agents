"""Parsing and refreshing of access tokens."""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass


@dataclass(frozen=True)
class TokenClaims:
    """Claims carried by an access token."""

    subject: str
    scopes: tuple[str, ...]
    expires_at: int

    def is_expired(self, now: int) -> bool:
        """Whether the token is expired at ``now`` in seconds since epoch."""
        return now >= self.expires_at

    def allows(self, scope: str) -> bool:
        """Whether the token grants ``scope``."""
        return scope in self.scopes


class TokenParser:
    """Decodes JSON web tokens without verifying their signature."""

    def parse(self, token: str) -> TokenClaims:
        """Decode ``token`` and return the claims it carries."""
        parts = token.split(".")
        if len(parts) != 3:
            raise ValueError("malformed token")
        payload = parts[1]
        padding = "=" * (-len(payload) % 4)
        try:
            raw = base64.urlsafe_b64decode(payload + padding)
            data = json.loads(raw)
        except ValueError as error:
            raise ValueError("the token payload is not valid JSON") from error
        return TokenClaims(
            subject=data.get("sub", ""),
            scopes=tuple(data.get("scopes", ())),
            expires_at=int(data.get("exp", 0)),
        )


class TokenRefresher:
    """Decides when an access token has to be refreshed before it is used."""

    def __init__(self, parser: TokenParser | None = None, refresh_margin_s: int = 60) -> None:
        self._parser = parser if parser is not None else TokenParser()
        self._refresh_margin_s = refresh_margin_s

    @property
    def refresh_margin_s(self) -> int:
        """Seconds before the expiry at which a token is refreshed."""
        return self._refresh_margin_s

    def needs_refresh(self, token: str, now: int) -> bool:
        """Whether ``token`` should be refreshed before it is used at ``now``."""
        claims = self._parser.parse(token)
        return claims.expires_at - now <= self._refresh_margin_s
