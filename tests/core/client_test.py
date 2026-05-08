"""Unit tests for core.client Redis utilities."""

import uuid
from datetime import timedelta
from unittest.mock import MagicMock

import pytest

from auth_user_service.core.client import (
    LoginRateLimiter,
    PKCEStore,
    RedisRateLimiter,
    RedisRefreshStore,
    RedisSessionManager,
)
from auth_sdk_m8.schemas.base import Period


class TestRedisRateLimiter:
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
        api_key_id = uuid.uuid4()
        key = self.limiter._key(api_key_id, Period.HOUR)
        assert Period.HOUR.value in key

    def test_key_day_period(self):
        api_key_id = uuid.uuid4()
        key = self.limiter._key(api_key_id, Period.DAY)
        assert Period.DAY.value in key

    def test_increment_first_call_sets_expire_minute(self):
        self.mock_redis.incr.return_value = 1
        api_key_id = uuid.uuid4()

        count = self.limiter.increment(api_key_id, Period.MINUTE)

        assert count == 1
        self.mock_redis.incr.assert_called_once()
        self.mock_redis.expire.assert_called_once()
        _, ttl = self.mock_redis.expire.call_args[0]
        assert ttl == 60

    def test_increment_first_call_sets_expire_hour(self):
        self.mock_redis.incr.return_value = 1
        api_key_id = uuid.uuid4()

        self.limiter.increment(api_key_id, Period.HOUR)

        _, ttl = self.mock_redis.expire.call_args[0]
        assert ttl == 3600

    def test_increment_first_call_sets_expire_day(self):
        self.mock_redis.incr.return_value = 1
        api_key_id = uuid.uuid4()

        self.limiter.increment(api_key_id, Period.DAY)

        _, ttl = self.mock_redis.expire.call_args[0]
        assert ttl == 86400

    def test_increment_subsequent_no_expire(self):
        self.mock_redis.incr.return_value = 2
        api_key_id = uuid.uuid4()

        count = self.limiter.increment(api_key_id, Period.MINUTE)

        assert count == 2
        self.mock_redis.expire.assert_not_called()

    def test_increment_returns_redis_count(self):
        self.mock_redis.incr.return_value = 42
        api_key_id = uuid.uuid4()

        count = self.limiter.increment(api_key_id, Period.HOUR)

        assert count == 42


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

    def test_pop_returns_verifier_and_deletes_key(self):
        self.mock_redis.get.return_value = "myverifier"

        result = self.store.pop("mystate")

        assert result == "myverifier"
        self.mock_redis.get.assert_called_once_with("pkce:mystate")
        self.mock_redis.delete.assert_called_once_with("pkce:mystate")

    def test_pop_returns_none_when_key_not_found(self):
        self.mock_redis.get.return_value = None

        result = self.store.pop("nonexistent")

        assert result is None
        self.mock_redis.delete.assert_not_called()

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

        result = self.limiter.is_allowed("user@example.com")

        assert result is True

    def test_is_allowed_exceeds_max_attempts(self):
        self.mock_redis.incr.return_value = 6

        result = self.limiter.is_allowed("user@example.com")

        assert result is False

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

    def test_rotate_deletes_old_and_registers_new_atomically(self):
        mock_pipe = MagicMock()
        self.mock_redis.pipeline.return_value = mock_pipe

        self.store.rotate("old-jti", "new-jti", 3600)

        self.mock_redis.pipeline.assert_called_once()
        mock_pipe.delete.assert_called_once_with("rt:old-jti")
        mock_pipe.setex.assert_called_once_with("rt:new-jti", 3600, "1")
        mock_pipe.execute.assert_called_once()

    def test_revoke_deletes_key(self):
        self.store.revoke("abc-jti")
        self.mock_redis.delete.assert_called_once_with("rt:abc-jti")

    def test_prefix_constant(self):
        assert RedisRefreshStore.PREFIX == "rt:"


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

        result = self.manager.is_blacklisted("some-jti")

        assert result is True
        self.mock_redis.exists.assert_called_once_with("jwt:blacklist:some-jti")

    def test_is_blacklisted_returns_false_when_not_exists(self):
        self.mock_redis.exists.return_value = 0

        result = self.manager.is_blacklisted("some-jti")

        assert result is False

    def test_prefix_constant(self):
        assert RedisSessionManager.PREFIX == "jwt:blacklist:"
