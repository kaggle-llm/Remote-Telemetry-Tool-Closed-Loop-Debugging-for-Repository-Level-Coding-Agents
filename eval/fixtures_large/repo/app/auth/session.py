"""The login session of a signed in reader."""

from __future__ import annotations

from dataclasses import dataclass

from app.auth.cache import Credential, CredentialCache
from app.auth.token import TokenRefresher


@dataclass(frozen=True)
class SignInResult:
    """The outcome of a sign in attempt."""

    scope: str
    credential: Credential


class SignInSession:
    """Keeps the credentials of the signed in reader.

    The session looks the credential of a scope up in the cache and
    checks the expiry of the access token before it hands the credential
    out, so an expired token never reaches the server.
    """

    def __init__(
        self,
        cache: CredentialCache | None = None,
        refresher: TokenRefresher | None = None,
        *,
        refresh_margin_s: int = 60,
    ) -> None:
        self._cache = cache if cache is not None else CredentialCache()
        self._refresher = (
            refresher if refresher is not None else TokenRefresher(refresh_margin_s=refresh_margin_s)
        )

    @property
    def cache(self) -> CredentialCache:
        """Cache that holds the credentials of the session."""
        return self._cache

    def sign_in(self, scope: str, token: str) -> SignInResult:
        """Store the credential of ``scope`` after a successful sign in."""
        credential = Credential(token=token, scope=scope)
        self._cache.put(scope, credential)
        return SignInResult(scope=scope, credential=credential)

    def credential_for(self, scope: str, now: int) -> Credential | None:
        """Return the credential of ``scope`` when it is still usable.

        A cached credential is only returned while its access token is
        valid; an expired token is dropped from the cache and the reader
        has to sign in again before the next request is sent.
        """
        credential = self._cache.get(scope)
        if credential is None:
            return None
        try:
            expired = self._refresher.needs_refresh(credential.token, now)
        except ValueError:
            expired = True
        if expired:
            self._cache.invalidate(scope)
            return None
        return credential

    def sign_out(self, scope: str) -> None:
        """Forget the credential of ``scope``."""
        self._cache.invalidate(scope)
