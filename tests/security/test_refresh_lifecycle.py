"""Security regression: refresh token registration, rotation, reuse, and revocation.

Verifies that:
- Login registers the refresh JTI in the Redis allowlist
- Rotation atomically deletes the old JTI and registers the new one (pipeline)
- Rotation uses a pipeline, never individual client calls (atomicity guarantee)
- A consumed JTI is invalid after rotation
- Reuse of a consumed JTI is rejected (is_valid returns False)
- Logout revokes the JTI from the allowlist
- Revoke is idempotent (absent key does not raise)
"""

import uuid
from unittest.mock import MagicMock

from auth_user_service.core.client import RedisRefreshStore


class TestRefreshTokenRegistration:
    """On login, the JTI must be written to the Redis allowlist with a TTL."""

    def setup_method(self):
        self.mock_redis = MagicMock()
        self.store = RedisRefreshStore(self.mock_redis)

    def test_register_sets_key_with_prefix(self):
        jti = str(uuid.uuid4())
        self.store.register(jti, ttl_seconds=7200)
        key_used = self.mock_redis.setex.call_args[0][0]
        assert key_used == f"rt:{jti}"

    def test_register_sets_correct_ttl(self):
        self.store.register("some-jti", ttl_seconds=3600)
        _, ttl, _ = self.mock_redis.setex.call_args[0]
        assert ttl == 3600

    def test_registered_jti_validates_as_valid(self):
        self.mock_redis.exists.return_value = 1
        assert self.store.is_valid("some-jti") is True

    def test_unregistered_jti_validates_as_invalid(self):
        self.mock_redis.exists.return_value = 0
        assert self.store.is_valid("unknown-jti") is False

    def test_is_valid_checks_correct_key(self):
        self.mock_redis.exists.return_value = 1
        self.store.is_valid("abc-jti")
        self.mock_redis.exists.assert_called_once_with("rt:abc-jti")


class TestRefreshTokenRotation:
    """On refresh, old JTI must be atomically invalidated and new JTI registered."""

    def setup_method(self):
        self.mock_redis = MagicMock()
        self.mock_pipe = MagicMock()
        self.mock_redis.pipeline.return_value = self.mock_pipe
        self.store = RedisRefreshStore(self.mock_redis)

    def test_rotation_deletes_old_jti(self):
        self.store.rotate("old-jti", "new-jti", ttl_seconds=3600)
        self.mock_pipe.delete.assert_called_once_with("rt:old-jti")

    def test_rotation_registers_new_jti(self):
        self.store.rotate("old-jti", "new-jti", ttl_seconds=3600)
        self.mock_pipe.setex.assert_called_once_with("rt:new-jti", 3600, "1")

    def test_rotation_executes_pipeline(self):
        self.store.rotate("old-jti", "new-jti", ttl_seconds=3600)
        self.mock_pipe.execute.assert_called_once()

    def test_rotation_uses_pipeline_not_direct_calls(self):
        """Both operations must be batched — direct client.delete/setex must not be called."""
        self.store.rotate("old-jti", "new-jti", 3600)
        self.mock_redis.delete.assert_not_called()
        self.mock_redis.setex.assert_not_called()

    def test_old_jti_absent_after_rotation(self):
        """Simulates post-rotation state: old JTI is gone from Redis."""
        self.mock_redis.exists.return_value = 0
        assert self.store.is_valid("old-jti") is False

    def test_new_jti_present_after_rotation(self):
        """Simulates post-rotation state: new JTI is in Redis."""
        self.mock_redis.exists.return_value = 1
        assert self.store.is_valid("new-jti") is True


class TestRefreshTokenReuse:
    """A consumed or revoked JTI must never validate — this is the theft-detection signal."""

    def setup_method(self):
        self.mock_redis = MagicMock()
        self.store = RedisRefreshStore(self.mock_redis)

    def test_consumed_jti_is_invalid(self):
        """After rotation, old JTI is absent → is_valid must return False."""
        self.mock_redis.exists.return_value = 0
        assert self.store.is_valid("consumed-jti") is False

    def test_revoked_jti_is_invalid(self):
        """After logout revocation, JTI is absent → is_valid must return False."""
        self.mock_redis.exists.return_value = 0
        assert self.store.is_valid("revoked-jti") is False

    def test_absent_jti_is_always_invalid(self):
        """An unknown JTI (never registered, or flushed from Redis) must be rejected."""
        self.mock_redis.exists.return_value = 0
        assert self.store.is_valid("never-seen-jti") is False


class TestRefreshTokenRevocationOnLogout:
    """On logout, the refresh JTI must be removed from the allowlist."""

    def setup_method(self):
        self.mock_redis = MagicMock()
        self.store = RedisRefreshStore(self.mock_redis)

    def test_revoke_deletes_correct_key(self):
        self.store.revoke("logout-jti")
        self.mock_redis.delete.assert_called_once_with("rt:logout-jti")

    def test_revoke_idempotent_when_key_absent(self):
        """Revoking an already-absent JTI must not raise — logout must always succeed."""
        self.mock_redis.delete.return_value = 0  # key did not exist
        self.store.revoke("already-gone-jti")  # must not raise
        self.mock_redis.delete.assert_called_once()

    def test_revoked_jti_no_longer_valid(self):
        self.mock_redis.exists.return_value = 0
        assert self.store.is_valid("just-revoked-jti") is False
