"""Unit tests for core.client Redis utilities."""

import uuid
from datetime import timedelta
from unittest.mock import MagicMock


from auth_user_service.core.client import (
    LoginRateLimiter,
    PKCEStore,
    RateLimitResult,
    RedisRateLimiter,
    RedisRefreshStore,
    RedisSessionManager,
)
from auth_sdk_m8.schemas.base import Period


class TestRedisRateLimiterKey:
    def setup_method(self):
        self.mock_redis = MagicMock()
        self.limiter = RedisRateLimiter(self.mock_redis)

    def test_key_contains_api_key_id_and_period(self):
        api_key_id = uuid.uuid4()
        key = self.limiter._key(api_key_id, Period.MINUTE)
        assert str(api_key_id) in key
        assert Period.MINUTE.value in key
        assert key.startswith("rate:")

    def test_key_hour_period(self):
        key = self.limiter._key(uuid.uuid4(), Period.HOUR)
        assert Period.HOUR.value in key

    def test_key_day_period(self):
        key = self.limiter._key(uuid.uuid4(), Period.DAY)
        assert Period.DAY.value in key

    def test_key_month_period(self):
        key = self.limiter._key(uuid.uuid4(), Period.MONTH)
        assert Period.MONTH.value in key

    def test_minute_and_hour_keys_differ(self):
        """Different periods must produce different bucket timestamps."""
        api_key_id = uuid.uuid4()
        k_min = self.limiter._key(api_key_id, Period.MINUTE)
        k_hour = self.limiter._key(api_key_id, Period.HOUR)
        assert k_min != k_hour


class TestRedisRateLimiterIncrement:
    """_increment() must use a pipeline so INCR+EXPIRE are atomic."""

    def setup_method(self):
        self.mock_redis = MagicMock()
        self.pipe = MagicMock()
        self.mock_redis.pipeline.return_value.__enter__ = MagicMock(
            return_value=self.pipe
        )
        self.mock_redis.pipeline.return_value.__exit__ = MagicMock(return_value=False)
        self.pipe.execute.return_value = (1, True)
        self.limiter = RedisRateLimiter(self.mock_redis)

    def test_increment_uses_pipeline(self):
        self.limiter._increment(uuid.uuid4(), Period.MINUTE)
        self.mock_redis.pipeline.assert_called_once()

    def test_increment_calls_incr_and_expire(self):
        self.limiter._increment(uuid.uuid4(), Period.MINUTE)
        self.pipe.incr.assert_called_once()
        self.pipe.expire.assert_called_once()

    def test_increment_sets_correct_ttl_minute(self):
        self.limiter._increment(uuid.uuid4(), Period.MINUTE)
        _, ttl = self.pipe.expire.call_args[0]
        assert ttl == 60

    def test_increment_sets_correct_ttl_hour(self):
        self.limiter._increment(uuid.uuid4(), Period.HOUR)
        _, ttl = self.pipe.expire.call_args[0]
        assert ttl == 3600

    def test_increment_sets_correct_ttl_day(self):
        self.limiter._increment(uuid.uuid4(), Period.DAY)
        _, ttl = self.pipe.expire.call_args[0]
        assert ttl == 86400

    def test_increment_sets_correct_ttl_month(self):
        self.limiter._increment(uuid.uuid4(), Period.MONTH)
        _, ttl = self.pipe.expire.call_args[0]
        assert ttl == 32 * 86400

    def test_increment_returns_count_from_pipeline(self):
        self.pipe.execute.return_value = (7, True)
        count = self.limiter._increment(uuid.uuid4(), Period.MINUTE)
        assert count == 7


class TestCheckAndIncrement:
    def setup_method(self):
        self.mock_redis = MagicMock()
        self.pipe = MagicMock()
        self.mock_redis.pipeline.return_value.__enter__ = MagicMock(
            return_value=self.pipe
        )
        self.mock_redis.pipeline.return_value.__exit__ = MagicMock(return_value=False)
        self.limiter = RedisRateLimiter(self.mock_redis)

    def _set_count(self, count: int) -> None:
        self.pipe.execute.return_value = (count, True)

    def test_returns_allowed_when_under_limit(self):
        self._set_count(1)
        result = self.limiter.check_and_increment(
            uuid.uuid4(), limit=5, period=Period.MINUTE
        )
        assert result.allowed is True

    def test_returns_allowed_at_exact_limit(self):
        self._set_count(5)
        result = self.limiter.check_and_increment(
            uuid.uuid4(), limit=5, period=Period.MINUTE
        )
        assert result.allowed is True

    def test_returns_blocked_when_over_limit(self):
        self._set_count(6)
        result = self.limiter.check_and_increment(
            uuid.uuid4(), limit=5, period=Period.MINUTE
        )
        assert result.allowed is False
        assert result.exceeded_period == Period.MINUTE

    def test_remaining_is_zero_when_over_limit(self):
        self._set_count(10)
        result = self.limiter.check_and_increment(
            uuid.uuid4(), limit=5, period=Period.MINUTE
        )
        assert result.remaining == 0

    def test_remaining_reflects_unused_quota(self):
        self._set_count(3)
        result = self.limiter.check_and_increment(
            uuid.uuid4(), limit=10, period=Period.MINUTE
        )
        assert result.remaining == 7

    def test_limit_field_populated(self):
        self._set_count(1)
        result = self.limiter.check_and_increment(
            uuid.uuid4(), limit=100, period=Period.HOUR
        )
        assert result.limit == 100

    def test_reset_at_is_set(self):
        self._set_count(1)
        result = self.limiter.check_and_increment(
            uuid.uuid4(), limit=10, period=Period.MINUTE
        )
        assert result.reset_at is not None


class TestCheckAllLimits:
    def setup_method(self):
        self.mock_redis = MagicMock()
        self.pipe = MagicMock()
        self.mock_redis.pipeline.return_value.__enter__ = MagicMock(
            return_value=self.pipe
        )
        self.mock_redis.pipeline.return_value.__exit__ = MagicMock(return_value=False)
        self.limiter = RedisRateLimiter(self.mock_redis)

    def _set_counts(self, counts: list[int]) -> None:
        self.pipe.execute.side_effect = [(c, True) for c in counts]

    def test_all_pass_returns_first_result(self):
        self._set_counts([1, 1])
        result = self.limiter.check_all_limits(
            uuid.uuid4(),
            [(Period.MINUTE, 10), (Period.HOUR, 100)],
        )
        assert result.allowed is True
        assert result.limit == 10  # tightest (first) window

    def test_stops_at_first_exceeded_window(self):
        self._set_counts([11, 1])  # MINUTE exceeded
        result = self.limiter.check_all_limits(
            uuid.uuid4(),
            [(Period.MINUTE, 10), (Period.HOUR, 100)],
        )
        assert result.allowed is False
        assert result.exceeded_period == Period.MINUTE
        # HOUR should never have been incremented
        assert self.pipe.execute.call_count == 1

    def test_second_window_exceeded(self):
        self._set_counts([1, 101])  # HOUR exceeded
        result = self.limiter.check_all_limits(
            uuid.uuid4(),
            [(Period.MINUTE, 10), (Period.HOUR, 100)],
        )
        assert result.allowed is False
        assert result.exceeded_period == Period.HOUR

    def test_empty_limits_returns_allowed(self):
        result = self.limiter.check_all_limits(uuid.uuid4(), [])
        assert result.allowed is True


class TestRateLimitResult:
    def test_default_headers_empty(self):
        result = RateLimitResult(allowed=True)
        assert result.headers == {}

    def test_blocked_result_has_exceeded_period(self):
        result = RateLimitResult(allowed=False, exceeded_period=Period.DAY)
        assert result.exceeded_period == Period.DAY


class TestPKCEStore:
    def setup_method(self):
        self.mock_redis = MagicMock()
        self.store = PKCEStore(self.mock_redis)

    def test_store_sets_key_with_correct_prefix(self):
        self.store.store("mystate", "myverifier")
        args = self.mock_redis.setex.call_args[0]
        assert args[0] == "pkce:mystate"

    def test_store_passes_verifier(self):
        self.store.store("mystate", "myverifier")
        args = self.mock_redis.setex.call_args[0]
        assert args[2] == "myverifier"

    def test_store_uses_ttl(self):
        self.store.store("mystate", "myverifier")
        args = self.mock_redis.setex.call_args[0]
        assert args[1] == timedelta(minutes=10)

    def test_pop_returns_verifier_via_getdel(self):
        """pop() must use atomic GETDEL, not separate GET + DELETE."""
        self.mock_redis.getdel.return_value = "myverifier"

        result = self.store.pop("mystate")

        assert result == "myverifier"
        self.mock_redis.getdel.assert_called_once_with("pkce:mystate")
        self.mock_redis.get.assert_not_called()
        self.mock_redis.delete.assert_not_called()

    def test_pop_returns_none_when_key_not_found(self):
        self.mock_redis.getdel.return_value = None
        assert self.store.pop("nonexistent") is None

    def test_prefix_constant(self):
        assert PKCEStore.PREFIX == "pkce:"

    def test_ttl_constant(self):
        assert PKCEStore.TTL == timedelta(minutes=10)


class TestLoginRateLimiter:
    def setup_method(self):
        self.mock_redis = MagicMock()
        self.limiter = LoginRateLimiter(self.mock_redis)

    def test_key_format(self):
        key = self.limiter._key("user@example.com")
        assert key == "login:attempts:user@example.com"

    def test_is_allowed_first_attempt_sets_expiry(self):
        self.mock_redis.incr.return_value = 1

        result = self.limiter.is_allowed("user@example.com")

        assert result is True
        self.mock_redis.expire.assert_called_once()
        _, ttl = self.mock_redis.expire.call_args[0]
        assert ttl == 900

    def test_is_allowed_within_max_attempts(self):
        self.mock_redis.incr.return_value = 5
        assert self.limiter.is_allowed("user@example.com") is True

    def test_is_allowed_exceeds_max_attempts(self):
        self.mock_redis.incr.return_value = 6
        assert self.limiter.is_allowed("user@example.com") is False

    def test_is_allowed_subsequent_no_expire(self):
        self.mock_redis.incr.return_value = 3
        self.limiter.is_allowed("user@example.com")
        self.mock_redis.expire.assert_not_called()

    def test_reset_deletes_key(self):
        self.limiter.reset("user@example.com")
        self.mock_redis.delete.assert_called_once_with(
            "login:attempts:user@example.com"
        )

    def test_constants(self):
        assert LoginRateLimiter.MAX_ATTEMPTS == 5
        assert LoginRateLimiter.WINDOW_SECONDS == 900
        assert LoginRateLimiter.PREFIX == "login:attempts:"


class TestRedisRefreshStore:
    def setup_method(self):
        self.mock_redis = MagicMock()
        self.store = RedisRefreshStore(self.mock_redis)

    def test_register_stores_with_prefix_and_ttl(self):
        self.store.register("abc-jti", 3600)
        self.mock_redis.setex.assert_called_once_with("rt:abc-jti", 3600, "1")

    def test_is_valid_returns_true_when_key_exists(self):
        self.mock_redis.exists.return_value = 1
        assert self.store.is_valid("abc-jti") is True
        self.mock_redis.exists.assert_called_once_with("rt:abc-jti")

    def test_is_valid_returns_false_when_key_absent(self):
        self.mock_redis.exists.return_value = 0
        assert self.store.is_valid("abc-jti") is False

    def test_rotate_uses_lua_not_pipeline(self):
        self.mock_redis.eval.return_value = 1
        self.store.rotate("old-jti", "new-jti", 3600)
        self.mock_redis.eval.assert_called_once()
        self.mock_redis.pipeline.assert_not_called()

    def test_rotate_returns_true_when_old_jti_present(self):
        self.mock_redis.eval.return_value = 1
        assert self.store.rotate("old-jti", "new-jti", 3600) is True

    def test_rotate_returns_false_when_old_jti_absent(self):
        """Lua script returns 0 when old JTI is gone — race lost or reuse attack."""
        self.mock_redis.eval.return_value = 0
        assert self.store.rotate("old-jti", "new-jti", 3600) is False

    def test_rotate_passes_correct_keys_and_ttl(self):
        self.mock_redis.eval.return_value = 1
        self.store.rotate("old-jti", "new-jti", 3600)
        args = self.mock_redis.eval.call_args[0]
        assert args[1] == 2  # numkeys
        assert args[2] == "rt:old-jti"
        assert args[3] == "rt:new-jti"
        assert args[4] == "3600"

    def test_revoke_deletes_key(self):
        self.store.revoke("abc-jti")
        self.mock_redis.delete.assert_called_once_with("rt:abc-jti")

    def test_prefix_constant(self):
        assert RedisRefreshStore.PREFIX == "rt:"


class TestResetAt:
    """Cover the DAY and MONTH branches of RedisRateLimiter._reset_at."""

    def setup_method(self):
        self.mock_redis = MagicMock()
        self.pipe = MagicMock()
        self.mock_redis.pipeline.return_value.__enter__ = MagicMock(
            return_value=self.pipe
        )
        self.mock_redis.pipeline.return_value.__exit__ = MagicMock(return_value=False)
        self.pipe.execute.return_value = (1, True)
        self.limiter = RedisRateLimiter(self.mock_redis)

    def test_day_reset_at_is_next_midnight(self):
        result = self.limiter.check_and_increment(
            uuid.uuid4(), limit=10, period=Period.DAY
        )
        assert result.reset_at is not None
        assert result.reset_at.hour == 0
        assert result.reset_at.minute == 0
        assert result.reset_at.second == 0

    def test_month_reset_at_is_first_of_next_month(self):
        result = self.limiter.check_and_increment(
            uuid.uuid4(), limit=10, period=Period.MONTH
        )
        assert result.reset_at is not None
        assert result.reset_at.day == 1
        assert result.reset_at.hour == 0

    def test_month_december_wraps_to_january(self):
        from datetime import datetime as _dt, timezone
        from unittest.mock import patch

        frozen = _dt(2025, 12, 15, 10, 30, 0, tzinfo=timezone.utc)
        with patch("auth_user_service.core.client.datetime") as mock_dt:
            mock_dt.now.return_value = frozen
            result = self.limiter._reset_at(Period.MONTH)

        assert result.year == 2026
        assert result.month == 1
        assert result.day == 1


class TestRedisSessionManager:
    def setup_method(self):
        self.mock_redis = MagicMock()
        self.manager = RedisSessionManager(self.mock_redis)

    def test_blacklist_jti_stores_with_ttl(self):
        self.manager.blacklist_jti("some-jti", 300)
        self.mock_redis.setex.assert_called_once_with(
            "jwt:blacklist:some-jti", 300, "revoked"
        )

    def test_is_blacklisted_returns_true_when_exists(self):
        self.mock_redis.exists.return_value = 1
        assert self.manager.is_blacklisted("some-jti") is True
        self.mock_redis.exists.assert_called_once_with("jwt:blacklist:some-jti")

    def test_is_blacklisted_returns_false_when_not_exists(self):
        self.mock_redis.exists.return_value = 0
        assert self.manager.is_blacklisted("some-jti") is False

    def test_prefix_constant(self):
        assert RedisSessionManager.PREFIX == "jwt:blacklist:"
