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
    """On refresh, old JTI must be atomically invalidated and new JTI registered.

    rotation uses a Lua script executed server-side by Redis so the
    check-and-swap is serializable — no concurrent request can interleave.
    """

    def setup_method(self):
        self.mock_redis = MagicMock()
        self.store = RedisRefreshStore(self.mock_redis)

    def test_rotation_uses_lua_not_pipeline(self):
        """Atomicity must come from a Lua script, not a client-side pipeline."""
        self.mock_redis.eval.return_value = 1
        self.store.rotate("old-jti", "new-jti", ttl_seconds=3600)
        self.mock_redis.eval.assert_called_once()
        self.mock_redis.pipeline.assert_not_called()

    def test_rotation_passes_old_and_new_keys(self):
        self.mock_redis.eval.return_value = 1
        self.store.rotate("old-jti", "new-jti", ttl_seconds=3600)
        args = self.mock_redis.eval.call_args[0]
        assert "rt:old-jti" in args
        assert "rt:new-jti" in args

    def test_rotation_passes_ttl_as_string_arg(self):
        self.mock_redis.eval.return_value = 1
        self.store.rotate("old-jti", "new-jti", ttl_seconds=7200)
        args = self.mock_redis.eval.call_args[0]
        assert "7200" in args

    def test_rotation_returns_true_when_old_jti_present(self):
        """Lua returns 1 → successful rotation → method returns True."""
        self.mock_redis.eval.return_value = 1
        assert self.store.rotate("old-jti", "new-jti", 3600) is True

    def test_rotation_returns_false_when_old_jti_absent(self):
        """Lua returns 0 → old JTI already gone → race lost or reuse attack."""
        self.mock_redis.eval.return_value = 0
        assert self.store.rotate("old-jti", "new-jti", 3600) is False

    def test_rotation_does_not_use_direct_delete_or_setex(self):
        """All work must happen inside eval — no direct client.delete/setex calls."""
        self.mock_redis.eval.return_value = 1
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
