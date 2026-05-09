"""
core.redis_db

This module provides Redis-backed utilities for:
1. API rate limiting using a fixed window algorithm.
2. JWT session and revocation management.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Final, Optional

from redis import Redis

from auth_sdk_m8.schemas.base import Period


class RedisRateLimiter:
    """
    Provides fast, in-memory API rate limiting using Redis.
    """

    _EXPIRATION_SECONDS: Final[dict[Period, int]] = {
        Period.MINUTE: 60,
        Period.HOUR: 3600,
        Period.DAY: 86400,
    }

    def __init__(self, client: Redis) -> None:
        """
        Initialize the RedisRateLimiter.

        Args:
            client (Redis, optional): Redis client. If None, use default from core.deps.
        """
        self.client = client

    def _key(self, api_key_id: uuid.UUID, period: Period) -> str:
        """
        Construct a unique Redis key for the given API key and time period.

        Args:
            api_key_id (uuid.UUID): The UUID of the API key.
            period (Period): The rate limit period.

        Returns:
            str: A Redis key string.
        """
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M")
        return f"rate:{api_key_id}:{period.value}:{timestamp}"

    def increment(self, api_key_id: uuid.UUID, period: Period) -> int:
        """
        Increments the usage count for the given API key and period.
        Sets an expiration if it's the first usage in that window.

        Args:
            api_key_id (uuid.UUID): The UUID of the API key.
            period (Period): The rate limit period.

        Returns:
            int: The current usage count.
        """
        key = self._key(api_key_id, period)
        count = self.client.incr(key)
        if count == 1:
            self.client.expire(key, self._EXPIRATION_SECONDS[period])
        return count


class PKCEStore:
    """
    Persistent store for PKCE code_verifiers, using Redis with TTL.
    """

    def __init__(self, client: Redis) -> None:
        """
        Initialize the RedisRateLimiter.

        Args:
            client (Redis, optional): Redis client. If None, use default from core.deps.
        """
        self.client = client

    PREFIX = "pkce:"
    TTL = timedelta(minutes=10)

    def store(self, state: str, code_verifier: str) -> None:
        """
        Store the code_verifier in Redis with a TTL.
        """
        key = self.PREFIX + state
        self.client.setex(key, self.TTL, code_verifier)

    def pop(self, state: str) -> Optional[str]:
        """
        Retrieve and delete the code_verifier from Redis using the state.
        """
        key = self.PREFIX + state
        code_verifier = self.client.get(key)
        if code_verifier is not None:
            # Delete after retrieval to prevent replay
            self.client.delete(key)
            return code_verifier
        return None


class LoginRateLimiter:
    """
    Fixed-window login attempt limiter keyed by email address.

    Blocks credential-stuffing / brute-force on a per-account basis.
    """

    MAX_ATTEMPTS: Final[int] = 5
    WINDOW_SECONDS: Final[int] = 900  # 15 minutes
    PREFIX: Final[str] = "login:attempts:"
    MAX_ID_LEN: Final[int] = 255

    def __init__(self, client: Redis) -> None:
        self.client = client

    def _key(self, identifier: str) -> str:
        # Strip control chars (including CRLF) and cap length to prevent
        # Redis key namespace pollution and memory exhaustion attacks.
        safe = "".join(c for c in identifier if c.isprintable())
        return f"{self.PREFIX}{safe[: self.MAX_ID_LEN]}"

    def is_allowed(self, identifier: str) -> bool:
        """
        Increment the attempt counter and return True if still within limit.

        Sets the expiry on the first attempt so the window is self-cleaning.
        """
        key = self._key(identifier)
        count = self.client.incr(key)
        if count == 1:
            self.client.expire(key, self.WINDOW_SECONDS)
        return count <= self.MAX_ATTEMPTS

    def reset(self, identifier: str) -> None:
        """Clear the counter after a successful login."""
        self.client.delete(self._key(identifier))


class RedisRefreshStore:
    """Allowlist-based refresh token store backed by Redis.

    Each active refresh JTI is registered as a Redis key with a TTL matching
    the token's remaining lifetime.  Rotation atomically removes the consumed
    JTI and registers the replacement — making reuse detectable immediately.

    This inverts the blacklist approach used by ``RedisSessionManager``:
    an absent key means the token is unknown/revoked (safe-fail when Redis
    is flushed), whereas a present key confirms the token is active.
    """

    PREFIX: Final[str] = "rt:"

    def __init__(self, client: Redis) -> None:
        self.client = client

    def _key(self, jti: str) -> str:
        return f"{self.PREFIX}{jti}"

    def register(self, jti: str, ttl_seconds: int) -> None:
        """Mark *jti* as an active refresh token with the given TTL."""
        self.client.setex(self._key(jti), ttl_seconds, "1")

    def is_valid(self, jti: str) -> bool:
        """Return True if *jti* is a known, active refresh token."""
        return bool(self.client.exists(self._key(jti)))

    def rotate(self, old_jti: str, new_jti: str, ttl_seconds: int) -> None:
        """Atomically invalidate *old_jti* and register *new_jti*.

        Using a pipeline ensures both operations succeed or fail together,
        preventing a window where neither JTI is valid.
        """
        pipe = self.client.pipeline()
        pipe.delete(self._key(old_jti))
        pipe.setex(self._key(new_jti), ttl_seconds, "1")
        pipe.execute()

    def revoke(self, jti: str) -> None:
        """Permanently revoke *jti* (e.g. on explicit logout)."""
        self.client.delete(self._key(jti))


class RedisSessionManager:
    """
    Manages token revocation via a Redis-backed blacklist.
    """

    def __init__(self, client: Redis) -> None:
        """
        Initialize the RedisSessionManager.

        Args:
            client (Redis, optional): Redis client. If None, use default from core.deps.
        """
        self.client = client

    PREFIX = "jwt:blacklist:"

    def blacklist_jti(self, jti: str, ttl: int) -> None:
        """
        Add a JWT token identifier (JTI) to the Redis blacklist.

        Args:
            jti (str): The unique JWT identifier.
            ttl (int): Time-to-live in seconds.
        """
        self.client.setex(f"{self.PREFIX}{jti}", ttl, "revoked")

    def is_blacklisted(self, jti: str) -> bool:
        """
        Check if a given JWT identifier has been revoked.

        Args:
            jti (str): The unique JWT identifier.

        Returns:
            bool: True if blacklisted, False otherwise.
        """
        return bool(self.client.exists(f"{self.PREFIX}{jti}"))
