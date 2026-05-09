"""
Session Controller

Handles creation and management of secure user sessions using
Redis for revocation and SQLModel for persistence.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from redis import Redis
from sqlmodel import Session, select, delete
from auth_user_service.db_models.users import User
from auth_user_service.db_models.sessions import ClientSessionCreate, ClientSession
from auth_user_service.core.client import RedisRefreshStore, RedisSessionManager
from auth_user_service.core.deps import CurrentUser, get_redis_client

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


class SessionController:
    """Manage user login sessions combining DB and Redis logic."""

    @staticmethod
    def create_client_session(
        *, session: Session, current_user: User, session_data: ClientSessionCreate
    ) -> ClientSession:
        """
        Persist a new session for the current user, storing both
        internal JWT tokens and external Google tokens, and
        register the internal JTI in Redis for revocation.

        Args:
            session (Session): SQLModel DB session.
            current_user (User): Authenticated user.
            session_data (ClientSessionCreate): Session details.

        Returns:
            ClientSession: The newly created session record.
        """
        statement = select(ClientSession).where(
            ClientSession.user_id == current_user.id
        )
        db_session = session.exec(statement).first()
        if db_session is not None:
            # Session already exists, update it
            db_session.provider = current_user.provider
            db_session.jwt_jti = session_data.jwt_jti
            db_session.refresh_token_hash = session_data.refresh_token_hash
            db_session.jwt_expires_at = session_data.jwt_expires_at
            db_session.refresh_expires_at = session_data.refresh_expires_at
            db_session.external_access_token = session_data.external_access_token
            db_session.external_refresh_token = session_data.external_refresh_token
            db_session.external_token_expires_at = (
                session_data.external_token_expires_at
            )
        else:
            db_session = ClientSession(
                user_id=current_user.id,
                provider=current_user.provider,
                jwt_jti=session_data.jwt_jti,
                refresh_token_hash=session_data.refresh_token_hash,
                jwt_expires_at=session_data.jwt_expires_at,
                refresh_expires_at=session_data.refresh_expires_at,
                external_access_token=session_data.external_access_token,
                external_refresh_token=session_data.external_refresh_token,
                external_token_expires_at=session_data.external_token_expires_at,
                revoked=False,
            )
        session.add(db_session)
        session.commit()
        session.refresh(db_session)

        return db_session

    @staticmethod
    def revoke_session_jti(jti: str, expires_at: datetime) -> None:
        """
        Blacklist a JWT identifier via Redis (manual revocation).

        Args:
            jti (str): JWT token identifier.
            expires_at (datetime): When the token would naturally expire.
        """
        now = datetime.now(timezone.utc)

        if expires_at.tzinfo is None:
            # assume UTC if naïve
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        raw_ttl = int((expires_at - now).total_seconds())
        if raw_ttl >= 0:
            safe_ttl = max(raw_ttl, 0)
            RedisSessionManager(get_redis_client()).blacklist_jti(jti, safe_ttl)
        else:
            logger.warning(
                "Not blacklisting JTI %s because TTL was %d seconds", jti, raw_ttl
            )

    @staticmethod
    def is_session_revoked(jti: str) -> bool:
        """
        Check if a JWT identifier is blacklisted.

        Args:
            jti (str): JWT token identifier.

        Returns:
            bool: True if token is blacklisted.
        """
        redis = RedisSessionManager(get_redis_client())
        return redis.is_blacklisted(jti)

    @staticmethod
    def delete_session_by_jti(session: Session, jti: str) -> None:
        """Delete the DB session record for the given JTI.

        Args:
            session: SQLModel DB session.
            jti: JWT identifier of the session to remove.
        """
        stmt = delete(ClientSession).where(ClientSession.jwt_jti == jti)
        session.exec(stmt)
        session.commit()

    @staticmethod
    def purge_expired_sessions(
        session: Session,
        current_user: CurrentUser,
    ) -> int:
        """
        Remove expired sessions from the database.

        Sessions are considered expired if their
        `refresh_expires_at` is before the current time.

        Args:
            session: SQLModel DB session.

        Returns:
            Number of sessions deleted.
        """
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        stmt = delete(ClientSession).where(
            ClientSession.user_id == current_user.id,
            ClientSession.refresh_expires_at < now,
        )
        result = session.exec(stmt)
        deleted = result.rowcount or 0
        if deleted:
            session.commit()
        return deleted

    @staticmethod
    def get_user_active_sessions(session: Session, user_id: str) -> list[ClientSession]:
        """
        Retrieve all non-revoked, non-expired sessions for a user.

        Args:
            session: SQLModel DB session.
            user_id: The user's UUID.

        Returns:
            List of active ClientSession objects.
        """
        now = datetime.now(timezone.utc)
        stmt = select(ClientSession).where(
            ClientSession.user_id == user_id,
            ClientSession.revoked == False,  # noqa: E712
            ClientSession.refresh_expires_at > now,
        )
        return session.exec(stmt).all()

    @staticmethod
    def revoke_all_user_sessions(
        session: Session, user_id: str, redis: Optional[Redis]
    ) -> int:
        """Revoke every active session for *user_id* — reuse-attack response.

        Blacklists all access JTIs and removes all refresh allowlist entries
        from Redis, then deletes the DB records.  Returns the number of
        sessions revoked.

        The access JTI and refresh JTI are the same value per token pair
        (``create_refresh_token`` is called with the access token's JTI), so
        ``ClientSession.jwt_jti`` covers both stores.

        Args:
            session: SQLModel DB session.
            user_id: UUID of the compromised user (string form).
            redis: Live Redis client, or None when Redis is unavailable.
        """
        active = SessionController.get_user_active_sessions(session, user_id)
        if redis is not None and active:
            access_mgr = RedisSessionManager(redis)
            refresh_store = RedisRefreshStore(redis)
            now = datetime.now(timezone.utc)
            for s in active:
                expires_at = s.jwt_expires_at
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=timezone.utc)
                ttl = int((expires_at - now).total_seconds())
                if ttl > 0:
                    access_mgr.blacklist_jti(s.jwt_jti, ttl)
                refresh_store.revoke(s.jwt_jti)

        stmt = delete(ClientSession).where(ClientSession.user_id == user_id)
        result = session.exec(stmt)
        session.commit()
        return result.rowcount or 0
