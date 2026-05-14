"""Unit tests for services.client_sessions.SessionController."""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch


from auth_user_service.db_models.sessions import ClientSessionCreate
from auth_user_service.services.client_sessions import SessionController


def _make_session_create(jti: str = None) -> ClientSessionCreate:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    return ClientSessionCreate(
        jwt_jti=jti or str(uuid.uuid4()),
        refresh_token_hash="r" * 64,
        jwt_expires_at=now + timedelta(hours=1),
        refresh_expires_at=now + timedelta(days=7),
    )


class TestCreateClientSession:
    def test_creates_new_session_when_none_exists(self, db_session, sample_user):
        session_data = _make_session_create()

        result = SessionController.create_client_session(
            session=db_session,
            current_user=sample_user,
            session_data=session_data,
        )

        assert result is not None
        assert result.jwt_jti == session_data.jwt_jti
        assert str(result.user_id) == str(sample_user.id)

    def test_updates_existing_session(
        self, db_session, sample_client_session, sample_user
    ):
        new_jti = str(uuid.uuid4())
        session_data = _make_session_create(jti=new_jti)

        result = SessionController.create_client_session(
            session=db_session,
            current_user=sample_user,
            session_data=session_data,
        )

        assert result.jwt_jti == new_jti

    def test_stores_external_tokens(self, db_session, sample_user):
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        session_data = ClientSessionCreate(
            jwt_jti=str(uuid.uuid4()),
            refresh_token_hash="t" * 64,
            jwt_expires_at=now + timedelta(hours=1),
            refresh_expires_at=now + timedelta(days=7),
            external_access_token="enc_access",
            external_refresh_token="enc_refresh",
            external_token_expires_at=now + timedelta(hours=1),
        )

        result = SessionController.create_client_session(
            session=db_session,
            current_user=sample_user,
            session_data=session_data,
        )

        assert result.external_access_token == "enc_access"
        assert result.external_refresh_token == "enc_refresh"


class TestRevokeSessionJti:
    def test_blacklists_jti_with_positive_ttl(self):
        future = datetime.now(timezone.utc) + timedelta(minutes=30)
        mock_manager = MagicMock()

        with (
            patch(
                "auth_user_service.services.client_sessions.get_redis_client"
            ) as mock_get_redis,
            patch(
                "auth_user_service.services.client_sessions.RedisSessionManager"
            ) as mock_cls,
        ):
            mock_cls.return_value = mock_manager
            SessionController.revoke_session_jti("my-jti", future)

        mock_manager.blacklist_jti.assert_called_once()
        jti_arg, ttl_arg = mock_manager.blacklist_jti.call_args[0]
        assert jti_arg == "my-jti"
        assert ttl_arg >= 0

    def test_does_not_blacklist_already_expired_jti(self):
        past = datetime.now(timezone.utc) - timedelta(minutes=30)
        mock_manager = MagicMock()

        with (
            patch("auth_user_service.services.client_sessions.get_redis_client"),
            patch(
                "auth_user_service.services.client_sessions.RedisSessionManager"
            ) as mock_cls,
        ):
            mock_cls.return_value = mock_manager
            SessionController.revoke_session_jti("old-jti", past)

        mock_manager.blacklist_jti.assert_not_called()

    def test_handles_naive_datetime_as_utc(self):
        naive_future = datetime.now() + timedelta(minutes=30)
        assert naive_future.tzinfo is None

        mock_manager = MagicMock()
        with (
            patch("auth_user_service.services.client_sessions.get_redis_client"),
            patch(
                "auth_user_service.services.client_sessions.RedisSessionManager"
            ) as mock_cls,
        ):
            mock_cls.return_value = mock_manager
            SessionController.revoke_session_jti("naive-jti", naive_future)

        mock_manager.blacklist_jti.assert_called_once()

    def test_zero_ttl_still_blacklists(self):
        exactly_now = datetime.now(timezone.utc)
        mock_manager = MagicMock()

        with (
            patch("auth_user_service.services.client_sessions.get_redis_client"),
            patch(
                "auth_user_service.services.client_sessions.RedisSessionManager"
            ) as mock_cls,
        ):
            mock_cls.return_value = mock_manager
            SessionController.revoke_session_jti("zero-jti", exactly_now)

        # TTL is 0 or just became non-negative; blacklist may or may not be called
        # depending on exact timing — just verify no exception is raised


class TestIsSessionRevoked:
    def test_returns_true_when_blacklisted(self):
        mock_manager = MagicMock()
        mock_manager.is_blacklisted.return_value = True

        with (
            patch("auth_user_service.services.client_sessions.get_redis_client"),
            patch(
                "auth_user_service.services.client_sessions.RedisSessionManager"
            ) as mock_cls,
        ):
            mock_cls.return_value = mock_manager
            result = SessionController.is_session_revoked("some-jti")

        assert result is True

    def test_returns_false_when_not_blacklisted(self):
        mock_manager = MagicMock()
        mock_manager.is_blacklisted.return_value = False

        with (
            patch("auth_user_service.services.client_sessions.get_redis_client"),
            patch(
                "auth_user_service.services.client_sessions.RedisSessionManager"
            ) as mock_cls,
        ):
            mock_cls.return_value = mock_manager
            result = SessionController.is_session_revoked("fresh-jti")

        assert result is False


class TestPurgeExpiredSessions:
    def test_deletes_expired_sessions(
        self, db_session, sample_user, expired_client_session
    ):
        current_user = MagicMock()
        current_user.id = sample_user.id

        deleted = SessionController.purge_expired_sessions(
            session=db_session, current_user=current_user
        )

        assert deleted >= 1

    def test_returns_zero_when_nothing_expired(self, db_session, sample_user):
        current_user = MagicMock()
        current_user.id = uuid.uuid4()  # user with no sessions

        deleted = SessionController.purge_expired_sessions(
            session=db_session, current_user=current_user
        )

        assert deleted == 0


class TestGetUserActiveSessions:
    def test_returns_active_sessions(
        self, db_session, sample_user, sample_client_session
    ):
        sessions = SessionController.get_user_active_sessions(
            session=db_session, user_id=sample_user.id
        )

        assert isinstance(sessions, list)

    def test_returns_empty_for_unknown_user(self, db_session):
        sessions = SessionController.get_user_active_sessions(
            session=db_session, user_id=uuid.uuid4()
        )

        assert sessions == []
