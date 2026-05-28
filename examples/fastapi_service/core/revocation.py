"""HTTP revocation client — checks JTI status via auth service private API."""

import logging

import httpx

_logger = logging.getLogger(__name__)


class RevocationCheckError(Exception):
    """Raised when the revocation check fails and fail-closed mode is configured."""


class RemoteRevocationClient:
    """Async HTTP client that posts a JTI to the auth service introspection endpoint.

    Fail-open by default: unreachable auth service → token treated as active.
    Set fail_closed=True to reject tokens when the endpoint is unavailable.
    """

    def __init__(
        self,
        *,
        introspection_url: str,
        private_api_secret: str,
        connect_timeout: float = 2.0,
        read_timeout: float = 3.0,
        fail_closed: bool = False,
    ) -> None:
        self._url = introspection_url
        self._fail_closed = fail_closed
        self._client = httpx.AsyncClient(
            headers={"X-Internal-Token": private_api_secret},
            timeout=httpx.Timeout(
                connect=connect_timeout, read=read_timeout, write=2.0, pool=2.0
            ),
        )

    async def is_revoked(self, jti: str) -> bool:
        """Return True when the JTI has been revoked.

        On network/HTTP error: returns False (fail-open) unless fail_closed=True,
        in which case RevocationCheckError is raised.
        """
        try:
            response = await self._client.post(self._url, json={"jti": jti})
            response.raise_for_status()
            return not response.json()["active"]
        except Exception as exc:
            _logger.warning("revocation.check_failed jti=%s error=%s", jti, exc)
            if self._fail_closed:
                raise RevocationCheckError(str(exc)) from exc
            return False

    async def close(self) -> None:
        """Close the underlying httpx session."""
        await self._client.aclose()
