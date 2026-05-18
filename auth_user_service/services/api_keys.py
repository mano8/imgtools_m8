"""API key service layer.

Responsibilities:
- Secure key generation and hash verification
- DB lookups for active keys
- Rate limit resolution (per-key → per-user → settings defaults)
- Rate limit enforcement with Redis and Prometheus metrics wiring
"""

import logging
import secrets
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from redis import Redis
from sqlmodel import Session, select

from auth_sdk_m8.observability import metrics as _metrics
from auth_sdk_m8.schemas.base import Period
from auth_user_service.core.client import RateLimitResult, RedisRateLimiter
from auth_user_service.core.security import SecurityHelper
from auth_user_service.db_models.api_keys import ApiKey, RateLimit

if TYPE_CHECKING:
    from auth_user_service.core.config import Settings

_logger = logging.getLogger(__name__)

# Ordered from finest to coarsest — enforced in this order so a MINUTE
# burst is caught before checking HOUR, giving the tightest feedback.
_PERIOD_ORDER: list[Period] = [
    Period.MINUTE,
    Period.HOUR,
    Period.DAY,
    Period.MONTH,
]


def _emit_validation_metric(label: str) -> None:
    m = _metrics.get()
    if m and m.api_key_validations_total:
        m.api_key_validations_total.labels(result=label).inc()


def _emit_rate_check_metric(label: str) -> None:
    m = _metrics.get()
    if m and m.api_key_rate_limit_checks_total:
        m.api_key_rate_limit_checks_total.labels(result=label).inc()


def _emit_rate_hit_metric(exceeded_period: Optional[Period]) -> None:
    m = _metrics.get()
    if m and m.api_key_rate_limit_hits_total and exceeded_period:
        m.api_key_rate_limit_hits_total.labels(period=exceeded_period.value).inc()


class ApiKeyService:
    """Handles creation, validation, and revocation of API keys."""

    KEY_PREFIX = "ak_"

    @classmethod
    def generate_key(cls) -> tuple[str, str]:
        """Generate a new API key and its SHA-256 hash.

        Returns:
            (plaintext, sha256_hex) — plaintext is shown to the user once
            and never stored; sha256_hex is persisted in the database.
        """
        plaintext = cls.KEY_PREFIX + uuid.uuid4().hex
        key_hash = SecurityHelper.hash_token(plaintext)
        return plaintext, key_hash

    @staticmethod
    def verify_key(plaintext: str, stored_hash: str) -> bool:
        """Constant-time comparison to prevent timing attacks."""
        candidate = SecurityHelper.hash_token(plaintext)
        return secrets.compare_digest(candidate, stored_hash)

    @staticmethod
    def get_active_key(session: Session, plaintext: str) -> Optional[ApiKey]:
        """Look up an API key by plaintext value.

        Increments the api_key_validations_total metric with the appropriate
        result label. Returns None for any non-success outcome.
        """
        key_hash = SecurityHelper.hash_token(plaintext)
        api_key = session.exec(
            select(ApiKey).where(ApiKey.key_hash == key_hash)
        ).first()

        if api_key is None:
            _emit_validation_metric("invalid")
            return None

        if api_key.revoked:
            _emit_validation_metric("revoked")
            return None

        now = datetime.now(timezone.utc)
        if api_key.expires_at and api_key.expires_at.replace(tzinfo=timezone.utc) < now:
            _emit_validation_metric("expired")
            return None

        _emit_validation_metric("success")
        return api_key

    @staticmethod
    def get_limits(
        session: Session,
        api_key_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> list[tuple[Period, int]]:
        """Resolve rate limits for a key using the priority chain.

        Priority: per-key RateLimit rows > per-user RateLimit rows.
        Falls back to an empty list (caller uses settings defaults).
        Returns periods in _PERIOD_ORDER order.
        """
        stmt = select(RateLimit).where(
            (RateLimit.api_key_id == api_key_id) | (RateLimit.user_id == user_id)
        )
        rows = session.exec(stmt).all()

        # Build a dict: period → (limit, is_key_specific)
        resolved: dict[Period, tuple[int, bool]] = {}
        for row in rows:
            is_key = row.api_key_id == api_key_id
            period = row.period
            existing = resolved.get(period)
            if existing is None or (is_key and not existing[1]):
                # Key-specific overrides user-level defaults
                resolved[period] = (row.limit, is_key)

        return [(p, resolved[p][0]) for p in _PERIOD_ORDER if p in resolved]


class RateLimitEnforcer:
    """Enforces rate limits using Redis counters and emits Prometheus metrics."""

    def __init__(self, redis: Redis, settings: "Settings") -> None:  # type: ignore[name-defined]
        self._limiter = RedisRateLimiter(redis)
        self._settings = settings

    def enforce(
        self,
        api_key: ApiKey,
        limits: list[tuple[Period, int]],
    ) -> RateLimitResult:
        """Check all rate limit windows and emit metrics.

        Increments checks_total BEFORE branching so the ratio
        allowed / checks_total remains stable on exception paths.

        Args:
            api_key: The validated API key.
            limits: Per-period limits from ApiKeyService.get_limits().
                    Falls back to settings defaults when empty.

        Returns:
            RateLimitResult — callers raise 429 when result.allowed is False.
        """
        # Resolve effective limits (DB overrides → settings defaults)
        effective = limits or self._default_limits()

        # Increment checks_total before branching (invariant: checks >= allowed + blocked)
        _emit_rate_check_metric("checked")

        result = self._limiter.check_all_limits(api_key.id, effective)

        if result.allowed:
            _emit_rate_check_metric("allowed")
        else:
            _emit_rate_check_metric("blocked")
            _emit_rate_hit_metric(result.exceeded_period)
            _logger.warning(  # nosec B506
                "api_key.rate_limited id=%s period=%s",
                api_key.id,
                result.exceeded_period,
            )

        return result

    def _default_limits(self) -> list[tuple[Period, int]]:
        """Return settings-based default limits for all configured periods."""
        s = self._settings
        limits = []
        if s.API_KEY_DEFAULT_LIMIT_MINUTE > 0:
            limits.append((Period.MINUTE, s.API_KEY_DEFAULT_LIMIT_MINUTE))
        if s.API_KEY_DEFAULT_LIMIT_HOUR > 0:
            limits.append((Period.HOUR, s.API_KEY_DEFAULT_LIMIT_HOUR))
        if s.API_KEY_DEFAULT_LIMIT_DAY > 0:
            limits.append((Period.DAY, s.API_KEY_DEFAULT_LIMIT_DAY))
        if s.API_KEY_DEFAULT_LIMIT_MONTH > 0:
            limits.append((Period.MONTH, s.API_KEY_DEFAULT_LIMIT_MONTH))
        return limits
