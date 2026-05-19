"""
core.redis_db

This module provides Redis-backed utilities for:
1. API rate limiting using a fixed window algorithm.
2. JWT session and revocation management.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Final, Optional

from redis import Redis

from auth_sdk_m8.schemas.base import Period


@dataclass
class RateLimitResult:
    """Result of a rate limit enforcement check."""

    allowed: bool
    exceeded_period: Optional[Period] = None
    limit: Optional[int] = None
    remaining: Optional[int] = None
    reset_at: Optional[datetime] = None
    headers: dict = field(default_factory=dict)


class RedisRateLimiter:
    """Fixed-window API rate limiter backed by Redis."""

    # Bucket timestamp format per period — each window maps to exactly one key.
    # Using full-minute format for ALL periods was the previous bug: HOUR/DAY
    # created a new key every minute instead of accumulating in one window.
    _BUCKET_FORMAT: Final[dict[Period, str]] = {
        Period.MINUTE: "%Y%m%d%H%M",
        Period.HOUR: "%Y%m%d%H",
        Period.DAY: "%Y%m%d",
        Period.MONTH: "%Y%m",
    }

    _EXPIRATION_SECONDS: Final[dict[Period, int]] = {
        Period.MINUTE: 60,
        Period.HOUR: 3600,
        Period.DAY: 86400,
        Period.MONTH: 32 * 86400,  # 32 days — covers any calendar month
    }

    def __init__(self, client: Redis) -> None:
        """Initialize the RedisRateLimiter.

        Args:
            client: Redis client instance.
        """
        self.client = client

    def _key(self, api_key_id: uuid.UUID, period: Period) -> str:
        """Construct the Redis key for this api_key + period + current bucket."""
        bucket = datetime.now(timezone.utc).strftime(self._BUCKET_FORMAT[period])
        return f"rate:api:{api_key_id}:{period.value}:{bucket}"

    def _reset_at(self, period: Period) -> datetime:
        """Return the UTC datetime when the current window resets."""
        now = datetime.now(timezone.utc)
        if period == Period.MINUTE:
            return now.replace(second=0, microsecond=0) + timedelta(minutes=1)
        if period == Period.HOUR:
            return now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        if period == Period.DAY:
            return now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(
                days=1
            )
        # MONTH: first second of next month
        if now.month == 12:
            return now.replace(
                year=now.year + 1,
                month=1,
                day=1,
                hour=0,
                minute=0,
                second=0,
                microsecond=0,
            )
        return now.replace(
            month=now.month + 1, day=1, hour=0, minute=0, second=0, microsecond=0
        )

    def _increment(self, api_key_id: uuid.UUID, period: Period) -> int:
        """Atomically increment the window counter and set TTL on first call.

        Uses a pipeline so INCR + EXPIRE are issued together — avoids the
        race where a crash between the two calls leaves a key with no TTL.
        """
        key = self._key(api_key_id, period)
        ttl = self._EXPIRATION_SECONDS[period]
        with self.client.pipeline() as pipe:
            pipe.incr(key)
            pipe.expire(key, ttl)
            count, _ = pipe.execute()
        return count

    def check_and_increment(
        self, api_key_id: uuid.UUID, limit: int, period: Period
    ) -> RateLimitResult:
        """Increment the counter for one period and return the result.

        Increments checks_total before branching so the ratio
        allowed / checks_total remains well-defined even on exception paths.
        """
        count = self._increment(api_key_id, period)
        reset_at = self._reset_at(period)
        remaining = max(0, limit - count)
        allowed = count <= limit
        return RateLimitResult(
            allowed=allowed,
            exceeded_period=None if allowed else period,
            limit=limit,
            remaining=remaining,
            reset_at=reset_at,
        )

    def check_all_limits(
        self, api_key_id: uuid.UUID, limits: list[tuple[Period, int]]
    ) -> RateLimitResult:
        """Enforce all configured rate limit windows in order (MINUTE first).

        Stops at the first exceeded window. Returns the tightest window's
        result when all pass (useful for response header population).

        Callers must increment the checks_total metric BEFORE calling this.

        Args:
            api_key_id: The API key being rate-checked.
            limits: List of (Period, max_requests) tuples, ordered from
                    finest to coarsest granularity.

        Returns:
            RateLimitResult with allowed=True if all windows pass.
        """
        first_result: Optional[RateLimitResult] = None
        for period, max_requests in limits:
            result = self.check_and_increment(api_key_id, max_requests, period)
            if first_result is None:
                first_result = result
            if not result.allowed:
                return result
        return first_result or RateLimitResult(allowed=True)


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
        """Atomically retrieve and delete the code_verifier for *state*.

        Uses GETDEL so a concurrent second callback with the same state
        cannot retrieve the verifier after the first caller has taken it.
        Returns None if the state is unknown or already consumed.
        """
        return self.client.getdel(self.PREFIX + state)


class LoginRateLimiter:
    """
    Fixed-window login attempt limiter keyed by email address.

    Blocks credential-stuffing / brute-force on a per-account basis.
    """

    DEFAULT_MAX_REQUESTS: Final[int] = 5
    DEFAULT_WINDOW_SECONDS: Final[int] = 900  # 15 minutes
    PREFIX: Final[str] = "login:attempts:"
    MAX_ID_LEN: Final[int] = 255

    def __init__(
        self,
        client: Redis,
        max_requests: int = DEFAULT_MAX_REQUESTS,
        window_seconds: int = DEFAULT_WINDOW_SECONDS,
    ) -> None:
        self.client = client
        self.max_requests = max_requests
        self.window_seconds = window_seconds

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
            self.client.expire(key, self.window_seconds)
        return count <= self.max_requests

    def reset(self, identifier: str) -> None:
        """Clear the counter after a successful login."""
        self.client.delete(self._key(identifier))


class RefreshRateLimiter:
    """Fixed-window refresh attempt limiter keyed by user ID.

    Limits the rate of token rotation to prevent session integrity denial (C2):
    an attacker holding a captured refresh token cannot spam rotations to
    force continuous session revocation for the victim.
    """

    DEFAULT_MAX_REQUESTS: Final[int] = 10
    DEFAULT_WINDOW_SECONDS: Final[int] = 300  # 5 minutes
    PREFIX: Final[str] = "refresh:attempts:"

    def __init__(
        self,
        client: Redis,
        max_requests: int = DEFAULT_MAX_REQUESTS,
        window_seconds: int = DEFAULT_WINDOW_SECONDS,
    ) -> None:
        self.client = client
        self.max_requests = max_requests
        self.window_seconds = window_seconds

    def _key(self, user_id: str) -> str:
        return f"{self.PREFIX}{user_id}"

    def is_allowed(self, user_id: str) -> bool:
        """Increment the rotation counter and return True if still within limit.

        Counts successful and failed rotations alike — the goal is to bound
        the request rate, not just reject bad tokens.
        """
        key = self._key(user_id)
        count = self.client.incr(key)
        if count == 1:
            self.client.expire(key, self.window_seconds)
        return count <= self.max_requests


_ROTATE_SCRIPT = """
local old = KEYS[1]
local new = KEYS[2]
local ttl = tonumber(ARGV[1])
if redis.call('exists', old) == 0 then
  return 0
end
redis.call('del', old)
redis.call('setex', new, ttl, '1')
return 1
"""


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

    def rotate(self, old_jti: str, new_jti: str, ttl_seconds: int) -> bool:
        """Atomically invalidate *old_jti* and register *new_jti*.

        Executes a Lua script so the check-and-swap is serializable — no
        concurrent request can interleave between the existence check and
        the key swap.

        Returns True if the rotation succeeded.  Returns False if *old_jti*
        was already absent, indicating a concurrent rotation won the race or
        a genuine reuse attack.
        """
        result = self.client.eval(
            _ROTATE_SCRIPT,
            2,
            self._key(old_jti),
            self._key(new_jti),
            str(ttl_seconds),
        )
        return bool(result)

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
