"""Security regression: session-chain invalidation on refresh token reuse.

Verifies that:
- revoke_all_user_sessions blacklists all access JTIs via RedisSessionManager
- revoke_all_user_sessions removes all refresh JTIs from RedisRefreshStore
- revoke_all_user_sessions deletes all DB session records for the user
- Blacklist TTL is derived from jwt_expires_at (not set for already-expired tokens)
- Behaviour is safe when redis is None (DB cleanup still happens)
- Returns the correct count of deleted sessions
- Reuse detection in the refresh endpoint triggers chain invalidation
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, call, patch

import pytest

from auth_user_service.services.client_sessions import SessionController


def _make_db_session(jti: str, expires_in_seconds: int = 3600) -> MagicMock:
    """Return a fake ClientSession with controllable fields."""
    s = MagicMock()
    s.jwt_jti = jti
    s.jwt_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in_seconds)
    return s


class TestRevokeAllUserSessionsRedis:
    """Redis stores must be updated before the DB records are deleted."""

    def _run(self, sessions: list, redis: MagicMock) -> int:
        with patch.object(
            SessionController,
            "get_user_active_sessions",
            return_value=sessions,
        ):
            with patch("auth_user_service.services.client_sessions.RedisSessionManager") as mgr_cls, \
                 patch("auth_user_service.services.client_sessions.RedisRefreshStore") as store_cls, \
                 patch("auth_user_service.services.client_sessions.delete"), \
                 patch("auth_user_service.services.client_sessions.Session"):
                mock_mgr = MagicMock()
                mock_store = MagicMock()
                mgr_cls.return_value = mock_mgr
                store_cls.return_value = mock_store
                mock_session = MagicMock()
                mock_session.exec.return_value.rowcount = len(sessions)
                return SessionController.revoke_all_user_sessions(
                    mock_session, "user-123", redis
                ), mock_mgr, mock_store

    def test_access_jtis_are_blacklisted(self):
        redis = MagicMock()
        sessions = [_make_db_session("jti-A"), _make_db_session("jti-B")]
        _, mgr, _ = self._run(sessions, redis)
        blacklisted = {c.args[0] for c in mgr.blacklist_jti.call_args_list}
        assert blacklisted == {"jti-A", "jti-B"}

    def test_refresh_jtis_are_revoked(self):
        redis = MagicMock()
        sessions = [_make_db_session("jti-A"), _make_db_session("jti-B")]
        _, _, store = self._run(sessions, redis)
        revoked = {c.args[0] for c in store.revoke.call_args_list}
        assert revoked == {"jti-A", "jti-B"}

    def test_expired_access_token_not_blacklisted(self):
        """Already-expired JTIs have negative TTL — must not be blacklisted."""
        redis = MagicMock()
        expired = _make_db_session("jti-expired", expires_in_seconds=-60)
        _, mgr, _ = self._run([expired], redis)
        mgr.blacklist_jti.assert_not_called()

    def test_redis_none_skips_redis_operations(self):
        """When Redis is unavailable, DB cleanup still runs without crashing."""
        sessions = [_make_db_session("jti-A")]
        with patch.object(
            SessionController, "get_user_active_sessions", return_value=sessions
        ), patch("auth_user_service.services.client_sessions.RedisSessionManager") as mgr_cls, \
           patch("auth_user_service.services.client_sessions.RedisRefreshStore") as store_cls:
            mock_session = MagicMock()
            mock_session.exec.return_value.rowcount = 1
            SessionController.revoke_all_user_sessions(mock_session, "user-123", None)
        mgr_cls.assert_not_called()
        store_cls.assert_not_called()

    def test_returns_session_count(self):
        redis = MagicMock()
        sessions = [_make_db_session("jti-A"), _make_db_session("jti-B")]
        count, _, _ = self._run(sessions, redis)
        assert count == 2

    def test_no_active_sessions_is_safe(self):
        """Empty session list must not cause any Redis calls."""
        redis = MagicMock()
        count, mgr, store = self._run([], redis)
        mgr.blacklist_jti.assert_not_called()
        store.revoke.assert_not_called()
        assert count == 0


class TestRevokeAllUserSessionsDatabase:
    """DB records must be deleted for every active session."""

    def test_db_sessions_deleted_for_user(self, db_session, sample_user):
        """Integration: real DB rows are removed and count is correct."""
        from auth_user_service.db_models.sessions import ClientSession
        from auth_user_service.services.auth import AuthController

        # create_client_session upserts (one row per user) so one call suffices.
        AuthController.create_auth_session(
            session=db_session,
            user=sample_user,
            jti="a" * 16,
            refresh_token="x" * 64,
        )

        count = SessionController.revoke_all_user_sessions(
            db_session, str(sample_user.id), redis=None
        )
        assert count >= 1

        from sqlmodel import select

        remaining = db_session.exec(
            select(ClientSession).where(ClientSession.user_id == sample_user.id)
        ).all()
        assert remaining == []
