"""Tests for routes/profile.py — all runtime branches covered."""

import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from auth_user_service.db_models.users import UpdatePassword, UserUpdateMe
from auth_user_service.routes.profile import (
    delete_user_me,
    read_user_me,
    update_password_me,
    update_user_me,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _user(*, is_superuser: bool = False, user_id: uuid.UUID | None = None) -> MagicMock:
    m = MagicMock()
    m.id = user_id or uuid.uuid4()
    m.is_superuser = is_superuser
    return m


def _mock_session(db_user: object = None) -> MagicMock:
    s = MagicMock()
    s.get.return_value = db_user
    return s


# ---------------------------------------------------------------------------
# read_user_me
# ---------------------------------------------------------------------------


class TestReadUserMe:
    def test_returns_current_user(self) -> None:
        current_user = _user()
        assert read_user_me(current_user=current_user) is current_user


# ---------------------------------------------------------------------------
# update_user_me
# ---------------------------------------------------------------------------


class TestUpdateUserMe:
    def test_no_email_update_succeeds(self, db_session, sample_user) -> None:
        """No email in payload — conflict check skipped, update persisted."""
        user_in = UserUpdateMe(full_name="Updated Name")
        with patch("auth_user_service.routes.profile.UserController"):
            result = update_user_me(
                session=db_session,
                current_user=sample_user,
                user_in=user_in,
            )
        assert result.success is True

    def test_email_new_address_succeeds(self, db_session, sample_user) -> None:
        """Email not yet taken (get_user_by_email returns None) — no conflict."""
        user_in = UserUpdateMe(email="unique@example.com")
        with patch("auth_user_service.routes.profile.UserController") as mock_ctrl:
            mock_ctrl.get_user_by_email.return_value = None
            result = update_user_me(
                session=db_session,
                current_user=sample_user,
                user_in=user_in,
            )
        assert result.success is True

    def test_email_same_user_no_conflict(self, db_session, sample_user) -> None:
        """Email belongs to current user — not a conflict."""
        user_in = UserUpdateMe(email="same@example.com")
        with patch("auth_user_service.routes.profile.UserController") as mock_ctrl:
            # existing_user has the same id as current_user → no conflict
            mock_ctrl.get_user_by_email.return_value = sample_user
            result = update_user_me(
                session=db_session,
                current_user=sample_user,
                user_in=user_in,
            )
        assert result.success is True

    def test_email_conflict_raises_409(self, sample_user) -> None:
        """Email already used by a different user → 409."""
        other = _user(user_id=uuid.uuid4())
        user_in = UserUpdateMe(email="taken@example.com")
        session = _mock_session()
        with patch("auth_user_service.routes.profile.UserController") as mock_ctrl:
            mock_ctrl.get_user_by_email.return_value = other
            with pytest.raises(HTTPException) as exc:
                update_user_me(
                    session=session,
                    current_user=sample_user,
                    user_in=user_in,
                )
        assert exc.value.status_code == 409

    def test_db_user_not_found_raises_404(self, sample_user) -> None:
        """session.get returns None → 404."""
        session = _mock_session(db_user=None)
        user_in = UserUpdateMe(full_name="New Name")
        with patch("auth_user_service.routes.profile.UserController"):
            with pytest.raises(HTTPException) as exc:
                update_user_me(
                    session=session,
                    current_user=sample_user,
                    user_in=user_in,
                )
        assert exc.value.status_code == 404

    def test_generic_exception_delegated(self, sample_user) -> None:
        """Unexpected exception → delegated to handle_route_exception."""
        session = _mock_session(db_user=sample_user)
        session.commit.side_effect = RuntimeError("boom")
        user_in = UserUpdateMe(full_name="New Name")
        with (
            patch("auth_user_service.routes.profile.UserController"),
            patch(
                "auth_user_service.routes.profile.handle_route_exception"
            ) as mock_handle,
        ):
            mock_handle.return_value = MagicMock()
            update_user_me(
                session=session,
                current_user=sample_user,
                user_in=user_in,
            )
        mock_handle.assert_called_once()


# ---------------------------------------------------------------------------
# update_password_me
# ---------------------------------------------------------------------------

_PASS = "oldpassword12"
_NEW_PASS = "newpassword12"


class TestUpdatePasswordMe:
    def test_db_user_not_found_raises_404(self, sample_user) -> None:
        session = _mock_session(db_user=None)
        body = UpdatePassword(current_password=_PASS, new_password=_NEW_PASS)
        with pytest.raises(HTTPException) as exc:
            update_password_me(session=session, body=body, current_user=sample_user)
        assert exc.value.status_code == 404

    def test_wrong_password_raises_400(self, sample_user) -> None:
        session = _mock_session(db_user=sample_user)
        body = UpdatePassword(current_password=_PASS, new_password=_NEW_PASS)
        with patch("auth_user_service.routes.profile.SecurityHelper") as mock_sec:
            mock_sec.verify_password.return_value = False
            with pytest.raises(HTTPException) as exc:
                update_password_me(session=session, body=body, current_user=sample_user)
        assert exc.value.status_code == 400

    def test_same_password_raises_400(self, sample_user) -> None:
        session = _mock_session(db_user=sample_user)
        body = UpdatePassword(current_password=_PASS, new_password=_PASS)
        with patch("auth_user_service.routes.profile.SecurityHelper") as mock_sec:
            mock_sec.verify_password.return_value = True
            with pytest.raises(HTTPException) as exc:
                update_password_me(session=session, body=body, current_user=sample_user)
        assert exc.value.status_code == 400

    def test_success(self, sample_user) -> None:
        session = _mock_session(db_user=sample_user)
        body = UpdatePassword(current_password=_PASS, new_password=_NEW_PASS)
        with patch("auth_user_service.routes.profile.SecurityHelper") as mock_sec:
            mock_sec.verify_password.return_value = True
            mock_sec.get_password_hash.return_value = "new_hashed"
            result = update_password_me(
                session=session, body=body, current_user=sample_user
            )
        assert "Password" in result.message

    def test_generic_exception_delegated(self, sample_user) -> None:
        session = _mock_session(db_user=sample_user)
        session.commit.side_effect = RuntimeError("db exploded")
        body = UpdatePassword(current_password=_PASS, new_password=_NEW_PASS)
        with (
            patch("auth_user_service.routes.profile.SecurityHelper") as mock_sec,
            patch(
                "auth_user_service.routes.profile.handle_route_exception"
            ) as mock_handle,
        ):
            mock_sec.verify_password.return_value = True
            mock_sec.get_password_hash.return_value = "hashed"
            mock_handle.return_value = MagicMock()
            update_password_me(session=session, body=body, current_user=sample_user)
        mock_handle.assert_called_once()


# ---------------------------------------------------------------------------
# delete_user_me
# ---------------------------------------------------------------------------


class TestDeleteUserMe:
    def test_superuser_raises_403(self) -> None:
        current_user = _user(is_superuser=True)
        session = _mock_session()
        with pytest.raises(HTTPException) as exc:
            delete_user_me(session=session, current_user=current_user)
        assert exc.value.status_code == 403

    def test_db_user_not_found_raises_404(self, sample_user) -> None:
        session = _mock_session(db_user=None)
        with pytest.raises(HTTPException) as exc:
            delete_user_me(session=session, current_user=sample_user)
        assert exc.value.status_code == 404

    def test_success(self, sample_user) -> None:
        session = _mock_session(db_user=sample_user)
        result = delete_user_me(session=session, current_user=sample_user)
        assert "deleted" in result.message.lower()
        session.delete.assert_called_once_with(sample_user)
        session.commit.assert_called_once()

    def test_generic_exception_delegated(self, sample_user) -> None:
        session = _mock_session(db_user=sample_user)
        session.delete.side_effect = RuntimeError("boom")
        with patch(
            "auth_user_service.routes.profile.handle_route_exception"
        ) as mock_handle:
            mock_handle.return_value = MagicMock()
            delete_user_me(session=session, current_user=sample_user)
        mock_handle.assert_called_once()
